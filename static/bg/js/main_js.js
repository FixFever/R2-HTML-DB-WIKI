// Модуль управления темой
var ThemeManager = {
    THEME_KEY: 'theme',
    DARK_THEME_CLASS: 'dark-theme',
    
    // Метод инициализации темы до загрузки DOM
    initThemeImmediately: function() {
        var savedTheme = localStorage.getItem(this.THEME_KEY);
        
        // Если тема темная, добавляем классы немедленно
        if (savedTheme === 'dark') {
            // Добавляем классы до загрузки документа
            document.documentElement.classList.add(this.DARK_THEME_CLASS);
            document.body.classList.add(this.DARK_THEME_CLASS);
            
            // Добавляем критические стили для предотвращения мигания
            var style = document.createElement('style');
            
            document.head.appendChild(style);
        }
    },

    // Метод переключения темы
    toggleTheme: function() {
        // Звуковой эффект
        var soundEffect = new Audio('https://www.soundjay.com/buttons/sounds/button-30.mp3');

        // Проверяем текущее состояние темы
        var isDarkTheme = document.documentElement.classList.contains(this.DARK_THEME_CLASS);
        
        // Переключаем тему
        if (isDarkTheme) {
            document.documentElement.classList.remove(this.DARK_THEME_CLASS);
            document.body.classList.remove(this.DARK_THEME_CLASS);
            localStorage.setItem(this.THEME_KEY, 'light');
        } else {
            document.documentElement.classList.add(this.DARK_THEME_CLASS);
            document.body.classList.add(this.DARK_THEME_CLASS);
            localStorage.setItem(this.THEME_KEY, 'dark');
        }

        // Воспроизводим звук
        soundEffect.play().catch(function() {}); 

        // Добавляем эффект подпрыгивания кнопки
        var themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.classList.add('bouncing');
            setTimeout(function() {
                themeToggle.classList.remove('bouncing');
            }, 1000);
        }
    }
};

// Утилиты
var SearchUtils = {
    // Функция подсветки совпадений при поиске
    highlightMatch: function(text, searchTerm) {
        if (!searchTerm) return text;
        var escapedSearchTerm = searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        var regex = new RegExp('(' + escapedSearchTerm + ')', 'gi');
        return text.replace(regex, '<span class="highlight">$1</span>');
    }
};

// Менеджер инициализации компонентов
var ComponentInitializer = {
    // Список компонентов для инициализации с проверкой
    components: [
        'initializeKeyboardNavigation',
        'initializeDropdownMenu', 
        'initializeTooltips', 
        'initializeSpoilers', 
        'initializeSearch'
    ],

    // Метод инициализации всех компонентов
    initializeAll: function() {
        this.components.forEach(function(componentFunc) {
            if (typeof window[componentFunc] === 'function') {
                window[componentFunc]();
            }
        });
    }
};

// Общие утилиты для инициализации
var CommonUtils = {
    // Инициализация тултипов (если используется Bootstrap)
    initializeTooltips: function() {
        if ($ && $.fn.tooltip) {
            $('[data-toggle="tooltip"]').tooltip();
        }
    }
};

// Вызываем метод инициализации темы немедленно
ThemeManager.initThemeImmediately();

// Главный модуль инициализации
document.addEventListener('DOMContentLoaded', function() {
    // Настраиваем кнопку переключения темы
    var themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            ThemeManager.toggleTheme();
        });
    }

    // Инициализируем jQuery-компоненты
    $(document).ready(function() {
        // Инициализируем общие компоненты
        if (typeof ComponentInitializer !== 'undefined') {
            ComponentInitializer.initializeAll();
        }
        
        // Инициализируем тултипы
        if (typeof CommonUtils !== 'undefined') {
            CommonUtils.initializeTooltips();
        }
    });

    // JavaScript
    document.querySelector('.pagination-bottom').addEventListener('click', function(e) {
        // Находим все элементы Atropos
        const atroposElements = document.querySelectorAll('.atropos');
        
        // Добавляем класс для отключения анимаций
        atroposElements.forEach(element => {
            element.classList.add('no-transition');
        });
        
        // Опционально: удаляем класс через небольшую задержку,
        // если нужно восстановить анимации после клика
        setTimeout(() => {
            atroposElements.forEach(element => {
                element.classList.remove('no-transition');
            });
        }, 300); // Задержка соответствует длительности анимации
    });
});