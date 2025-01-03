from flask import Blueprint, render_template, current_app, abort, jsonify, request, current_app
import requests
from services.monster_service import (
    get_monster_by_id,
    get_monster_drops,
    get_monsters_by_class,
    get_monster_resource,
    get_monster_mtick,
    get_monsterabnormalResist_data,
    get_monster_attribute_add_data,
    get_monster_attribute_resist_data,
    get_monster_protect_data,
    get_monster_slain_data,
    get_monster_ai_data,
    get_monster_aiex_data,
    apply_monster_filters,
    monster_to_dict
    
)
from services.utils import get_google_sheets_data, with_app_context
from services.merchant_service import (
    get_merchant_items
)
from services.database import execute_query
from config.settings import MONSTER_CLASS_URL, MONSTER_RACE_URL, MONSTER_LOCATION_URL, MONSTER_MGBJ_TYPE_URL
import pandas as pd
from functools import wraps, partial
from concurrent.futures import ThreadPoolExecutor

bp = Blueprint('monsters', __name__)

# ! Словарь с маппингом URL -> конфигурация
MONSTER_ROUTES = {
    'monster_all': {
        'classes': list(range(1, 39)),  # Все классы монстров
        'title': '[Монстры] Все монстры',
        'header': 'Все монстры'
    },
    'monster_regular': {
        'classes': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22],
        'title': '[Монстры] Обычные монстры',
        'header': 'Обычные монстры'
    },
    'monster_boss': {
        'classes': [29, 38, 37, 36, 34],
        'title': '[Монстры] Боссы',
        'header': 'Боссы'
    },
    'monster_raidboss': {
    'classes': [26],
    'title': '[Монстры] Рейд-Боссы',
    'header': 'Рейд-Боссы'
    },
    'monster_imennoy': {
    'classes': [28],
    'title': '[Монстры] Именные-Боссы',
    'header': 'Именные-Боссы'
    },
    'monster_npc': {
        'classes': [23],
        'title': '[Монстры] NPC',
        'header': 'NPC'
    },
    'monster_event': {
        'classes': [27],
        'title': '[Монстры] Монстры события',
        'header': 'Монстры события'
    }
}


# ! Главная страница монстров
def with_monster_filters(allowed_classes):
    """Enhanced decorator for filtering with pagination and class restrictions"""
    def decorator(original_route):
        @wraps(original_route)
        def wrapped_route(*args, **kwargs):
            try:
                # Get search term
                search_term = request.args.get('search', '')
                
                monsters = []
                file_paths = {}
                
                # for monsters_type in allowed_classes:
                #     type_monsters, type_paths = get_monsters_by_class([monsters_type], search_term)
                #     monsters.extend(type_monsters)
                #     file_paths.update(type_paths)
                
                type_monsters, type_paths = get_monsters_by_class(allowed_classes, search_term)
                monsters.extend(type_monsters)
                file_paths.update(type_paths)
                
                
                # If it's an AJAX request, handle filtering
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    filters = request.args.to_dict()
                    
                    # Apply filters
                    filtered_monsters = apply_monster_filters(monsters, filters)

                    # Get pagination parameters
                    page = request.args.get('page', 1, type=int)
                    per_page = request.args.get('per_page', 25000, type=int) # ! PP LIMIT
                
                    # Apply pagination
                    start_idx = (page - 1) * per_page
                    end_idx = start_idx + per_page
                    paginated_monsters = filtered_monsters[start_idx:end_idx]
                    
                    # Convert to dict for response
                    monsters_dict = [monster_to_dict(item) for item in paginated_monsters]

                    return jsonify({
                        'monsters': monsters_dict,
                        'resources': file_paths,
                        'total': len(filtered_monsters),
                        'pages': (len(filtered_monsters) + per_page - 1) // per_page
                    })
                    
                # For normal request, pass data to route
                return original_route(items=monsters, item_resources=file_paths, *args, **kwargs)
                
            except Exception as e:
                print(f"Error in route: {str(e)}")
                import traceback
                traceback.print_exc()
                return jsonify({'error': str(e)}), 500
                
        return wrapped_route
    return decorator

@bp.route('/monster_<type>')
def monster_page(type):
    route_key = f'monster_{type}'
    config = MONSTER_ROUTES.get(route_key)
    
    if not config:
        abort(404)
        
    @with_monster_filters(config['classes'])
    def handle_monster_page(items=None, item_resources=None):
        # If it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                # Get filters from request
                filters = request.args.to_dict()
                
                # Apply filters
                filtered_monsters = apply_monster_filters(items, filters)
                
                # Get pagination parameters
                page = request.args.get('page', 1, type=int)
                per_page = request.args.get('per_page', 25000, type=int)
                
                # Calculate pagination
                start_idx = (page - 1) * per_page
                end_idx = start_idx + per_page
                paginated_monsters = filtered_monsters[start_idx:end_idx]
                
                # Convert monsters to dict for JSON response
                monsters_dict = [monster_to_dict(monster) for monster in paginated_monsters]
                
                return jsonify({
                    'monsters': monsters_dict,
                    'resources': item_resources,
                    'total': len(filtered_monsters),
                    'filtered': len(filtered_monsters),
                    'pages': (len(filtered_monsters) + per_page - 1) // per_page
                })
                
            except Exception as e:
                print(f"Error processing request: {str(e)}")
                import traceback
                traceback.print_exc()
                return jsonify({'error': str(e)}), 500
        
        # For normal page load
        return render_template(
            'monster_core/monster_page_route.html',
            items=items,
            item_resources=item_resources,
            title=config["title"],
            header=config['header']
        )
    
    return handle_monster_page()



# ! Страница детальной информации монстров
@bp.route('/monster/<int:monster_id>')
def monster_detail(monster_id: int):
    """Страница деталей монстра"""
    try:
        # Получение основного объекта монстра
        if not (monster := get_monster_by_id(monster_id)):
            return "Monster not found", 404

        # Преобразуем monster в словарь для удобства работы
        monster_dict = {
            'MID': monster.MID,
            'MName': monster.MName.replace('/n', ' '),
            'MClass': monster.MClass,
            'mLevel': monster.mLevel,
            'mExp': monster.MExp,
            'MHIT': monster.MHIT,
            'MMinD': monster.MMinD,
            'MMaxD': monster.MMaxD,
            'MAttackRateOrg': monster.MAttackRateOrg,
            'MMoveRateOrg': monster.MMoveRateOrg,
            'MHP': monster.MHP,
            'MMP': monster.MMP,
            'MMoveRange': monster.MMoveRange,
            'MRaceType': monster.MRaceType,
            'mSightRange': monster.mSightRange,
            'mAttackRange': monster.mAttackRange,
            'mSkillRange': monster.mSkillRange,
            'mScale': monster.mScale,
            'mIsEvent': monster.mIsEvent,
            'mIsTest': monster.mIsTest,
            'mHPRegen': monster.mHPRegen,
            'mMPRegen': monster.mMPRegen,
            'mIsShowHp': monster.mIsShowHp,
            'mAttackType': monster.mAttackType,
            'mVolitionOfHonor': monster.mVolitionOfHonor,
            'MAttackRateNew': monster.MAttackRateNew,
            'MMoveRateNew': monster.MMoveRateNew,
            'MGbjType': monster.MGbjType,
            'MAiType': monster.MAiType,
            'MCastingDelay': monster.MCastingDelay,
            'MChaotic': monster.MChaotic,
            'MSameRace1': monster.MSameRace1,
            'MSameRace2': monster.MSameRace2,
            'MSameRace3': monster.MSameRace3,
            'MSameRace4': monster.MSameRace4,
            'mBodySize': monster.mBodySize,
            'mDetectTransF': int(monster.mDetectTransF),
            'mDetectTransP': int(monster.mDetectTransP),
            'mDetectChao': int(monster.mDetectChao),
            'mAiEx': monster.mAiEx,
            'mIsResistTransF': int(monster.mIsResistTransF),
            'mHPNew': monster.mHPNew,
            'mMPNew': monster.mMPNew,
            'mBuyMerchanID': monster.mBuyMerchanID,
            'mSellMerchanID': monster.mSellMerchanID,
            'mChargeMerchanID': monster.mChargeMerchanID,
            'mTransformWeight': monster.mTransformWeight,
            'mNationOp': monster.mNationOp,
            'IContentsLv': monster.IContentsLv,
            'mIsEventTest': int(monster.mIsEventTest),
            'mSupportType': monster.mSupportType,
            'mWMapIconType': monster.mWMapIconType,
            'mIsAmpliableTermOfValidity': int(monster.mIsAmpliableTermOfValidity),
            'mTransType': monster.mTransType,
            'mDPV': monster.mDPV,
            'mMPV': monster.mMPV,
            'mRPV': monster.mRPV,
            'mDDV': monster.mDDV,
            'mMDV': monster.mMDV,
            'mRDV': monster.mRDV,
            'mSubDDWhenCritical': monster.mSubDDWhenCritical,
            'mEnemySubCriticalHit': monster.mEnemySubCriticalHit,
            'mEventQuest': int(monster.mEventQuest),
            'mEScale': monster.mEScale
        }

        # Получаем приложение для использования в контексте
        app = current_app._get_current_object()

        # Создаем ThreadPoolExecutor для параллельного выполнения задач
        with ThreadPoolExecutor(max_workers=20) as executor:
            # Оборачиваем каждую функцию в контекст приложения
            def submit_with_context(func, *args, **kwargs):
                return executor.submit(with_app_context, func, app, *args, **kwargs)

            # Запускаем параллельные задачи
            future_google_class = executor.submit(get_google_sheets_data, MONSTER_CLASS_URL)
            future_google_race = executor.submit(get_google_sheets_data, MONSTER_RACE_URL)
            future_google_location = executor.submit(get_google_sheets_data, MONSTER_LOCATION_URL)
            future_google_mgbj = executor.submit(get_google_sheets_data, MONSTER_MGBJ_TYPE_URL)

            
            
            future_merchant_items = submit_with_context(get_merchant_items, monster_id)
            future_monster_drops = submit_with_context(get_monster_drops, monster_id)
            future_monster_resource = submit_with_context(get_monster_resource, monster_id)
            future_abnormalResist = submit_with_context(get_monsterabnormalResist_data, monster_id)
            future_attribute_add = submit_with_context(get_monster_attribute_add_data, monster_id)
            future_attribute_resist = submit_with_context(get_monster_attribute_resist_data, monster_id)
            future_protect = submit_with_context(get_monster_protect_data, monster_id)
            future_slain = submit_with_context(get_monster_slain_data, monster_id)
            future_mtick_normal = submit_with_context(get_monster_mtick, monster_id, 0)
            future_mtick_event = submit_with_context(get_monster_mtick, monster_id, 1)
            future_ai_data = submit_with_context(get_monster_ai_data, monster_id)
            future_aiex_data = submit_with_context(get_monster_aiex_data, monster_id)

            # Получаем результаты Google Sheets
            sheets_data = {
                'class': future_google_class.result(),
                'race': future_google_race.result(),
                'location': future_google_location.result(),
                'mgbj': future_google_mgbj.result()
            }

            # Получение информации о классе
            class_info = {"MName": ""}
            if not sheets_data['class'].empty:
                class_match = sheets_data['class'][sheets_data['class']['MClass'] == monster_dict['MClass']]
                if not class_match.empty:
                    class_info["MName"] = class_match.iloc[0]['MName']

            # Получение информации о расе
            race_info = {"mDesc": None}
            if not sheets_data['race'].empty:
                race_match = sheets_data['race'][sheets_data['race']['MRaceType'] == monster_dict['MRaceType']]
                if not race_match.empty:
                    race_info["mDesc"] = race_match.iloc[0]['mDesc']

            # Получение локации монстра
            monster_location = []
            if not sheets_data['location'].empty:
                location_match = sheets_data['location'][sheets_data['location']['MID'] == monster_id]
                if not location_match.empty:
                    monster_location = [
                        {
                            "Location": row['mPlaceNmRus'],
                            "LocationLevel": None if pd.isna(row['mMapNmRus']) else row['mMapNmRus']
                        }
                        for _, row in location_match.iterrows()
                    ]

            # Получение MGbjType описание монстра
            mgbj_desc = None
            if not sheets_data['mgbj'].empty:
                mgbj_match = sheets_data['mgbj'][sheets_data['mgbj']['MGbjType'] == monster_dict['MGbjType']]
                if not mgbj_match.empty:
                    mgbj_desc = mgbj_match.iloc[0]['mDesc']
                        
            
            # Получаем результаты остальных задач
            merchant_items = future_merchant_items.result()
            monster_drops = future_monster_drops.result()
            model_result = future_monster_resource.result()
            monster_abnormalResist_data = future_abnormalResist.result()
            monster_attribute_add_data = future_attribute_add.result()
            monster_attribute_resist_data = future_attribute_resist.result()
            monster_protect_data = future_protect.result()
            monster_slain_data = future_slain.result()
            mTick_normal, mVarRespawnTick_normal = future_mtick_normal.result()
            mTick_event, mVarRespawnTick_event = future_mtick_event.result()
            ai_data=future_ai_data.result()
            aiex_data = future_aiex_data.result(),

            
            if isinstance(aiex_data, tuple) and len(aiex_data) > 0:
                aiex_data = aiex_data[0]
            
            
            # Обработка изображений
            file_path = f"{current_app.config['GITHUB_URL']}{monster_id}.png"
            file_path_gif = f"{current_app.config['GITHUB_URL']}gif/{monster_id}_IDLE.gif"
            try:
                if requests.head(file_path_gif).status_code != 200:
                    file_path_gif = None
            except:
                file_path_gif = None

            # Получение модели монстра
            prefix = 'm'  # Префикс по умолчанию для всех монстров
            monster_model_no = None
            if model_result:
                monster_model_no = f"{int(model_result.RFileName):05}"

            # Обработка времени респауна
            def get_respawn_info(time_in_seconds):
                hours = int(time_in_seconds / 60) // 60
                minutes = int(time_in_seconds / 60)
                
                if hours > 0 and minutes % 60 > 0:
                    formatted_time = f"{hours}ч {minutes % 60}м"
                elif hours > 0:
                    formatted_time = f"{hours}ч"
                elif minutes > 0:
                    formatted_time = f"{minutes}м"
                else:
                    formatted_time = f"{time_in_seconds} сек"
                    
                return {
                    "mTickMin": int(time_in_seconds / 60),
                    "mTickSec": time_in_seconds % 60,
                    "mTick": time_in_seconds,
                    "hours": hours,
                    "formatted_time": formatted_time
                }

            # Получение времени респауна
            respawn_info_normal = {}
            respawn_info_event = {}

            if mTick_normal > 0:
                respawn_info_normal = {
                    "normal": get_respawn_info(mTick_normal),
                    "event": get_respawn_info(mVarRespawnTick_normal)
                }

            if mTick_event > 0:
                respawn_info_event = {
                    "normal": get_respawn_info(mTick_event),
                    "event": get_respawn_info(mVarRespawnTick_event)
                }

        # Рендеринг шаблона
        return render_template(
            'monster_core/monster_page_detail.html',
            item=monster_dict,
            file_path=file_path,
            file_path_gif=file_path_gif,
            classinfo=class_info,
            raceinfo=race_info,
            respawn_info_normal=respawn_info_normal,
            respawn_info_event=respawn_info_event,
            monlocationinfo=monster_location,
            merchant_items=merchant_items,
            mondropinfo=monster_drops,
            monstermodelno_result=monster_model_no,
            monster_abnormalResist_data=monster_abnormalResist_data,
            monster_attribute_add_data=monster_attribute_add_data,
            monster_attribute_resist_data=monster_attribute_resist_data,
            monster_protect_data=monster_protect_data,
            monster_slain_data=monster_slain_data,
            mgbj_desc=mgbj_desc,
            ai_data=ai_data,
            aiex_data=aiex_data,
            prefix=prefix
        )
        
    except Exception as e:
        print(f"Error in monster detail route: {str(e)}")
        import traceback
        traceback.print_exc()
        return "Internal server error", 500
    
    

