import logging
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Список факультетов
FACULTIES = {
    "ФН": "Фундаментальные науки",
    "РЛ": "Радиолокация и радионавигация",
    "РК": "Ракетно-космическая техника",
    "ИБМ": "Инженерный бизнес и менеджмент",
    "ИУ": "Информатика и системы управления", 
    "СМ": "Специальное машиностроение",
    "МТ": "Машиностроительные технологии",
    "Э": "Энергомашиностроение",
    "Л": "Лингвистика",
    "БМТ": "Биомедицинская техника",
    "СГН": "Социальные и гуманитарные науки",
    "ГУИМЦ": "Головной учебно-исследовательский и методический центр",
    "ЮР": "Юриспруденция"
}

class DatingBot:
    def __init__(self):
        self.db_name = 'dating_bot.db'
        self.setup_database()
        self.user_states = {}

    def setup_database(self):
        """Создание базы данных и таблиц"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица анкет
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                photo_id TEXT,
                gender TEXT,
                faculty TEXT,
                age INTEGER,
                bio TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица лайков
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS likes (
                like_id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER,
                to_profile_id INTEGER,
                is_like BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ База данных создана!")

    def get_main_menu_keyboard(self):
        """Клавиатура главного меню"""
        keyboard = [
            [KeyboardButton("👤 Создать анкету")],
            [KeyboardButton("🔍 Найти анкету"), KeyboardButton("💝 Мои мэтчи")],
            [KeyboardButton("📊 Моя анкета"), KeyboardButton("❌ Удалить анкету")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def get_faculty_keyboard(self):
        """Клавиатура выбора факультета"""
        # Создаем 3 колонки для лучшего отображения
        buttons = []
        faculty_codes = list(FACULTIES.keys())
        
        # Разбиваем на строки по 3 элемента
        for i in range(0, len(faculty_codes), 3):
            row = []
            for code in faculty_codes[i:i+3]:
                row.append(InlineKeyboardButton(code, callback_data=f"faculty_{code}"))
            buttons.append(row)
        
        return InlineKeyboardMarkup(buttons)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        
        # Добавляем пользователя в БД
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (user.id, user.username, user.first_name, user.last_name))
        conn.commit()
        conn.close()
        
        welcome_text = (
            "👋 Добро пожаловать в бот знакомств!\n\n"
            "Здесь вы можете:\n"
            "• Создать свою анкету\n"
            "• Просматривать анкеты других пользователей\n"
            "• Ставить лайки и находить мэтчи\n\n"
            "Выберите действие в меню ниже:"
        )
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=self.get_main_menu_keyboard()
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        text = update.message.text
        
        if text == "👤 Создать анкету":
            await self.start_create_profile(update, context)
        elif text == "🔍 Найти анкету":
            await self.find_profile(update, context)
        elif text == "💝 Мои мэтчи":
            await self.show_matches(update, context)
        elif text == "📊 Моя анкета":
            await self.show_my_profile(update, context)
        elif text == "❌ Удалить анкету":
            await self.delete_profile(update, context)
        elif update.message.chat.id in self.user_states:
            # Обработка состояний при создании анкеты
            state = self.user_states[update.message.chat.id]['step']
            if state == 'waiting_name':
                await self.handle_name(update, context)
            elif state == 'waiting_age':
                await self.handle_age(update, context)
            elif state == 'waiting_bio':
                await self.handle_bio(update, context)

    async def start_create_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало создания анкеты"""
        user_id = update.effective_user.id
        
        # Проверяем, есть ли уже анкета
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM profiles WHERE user_id = ? AND is_active = TRUE', (user_id,))
        existing_profile = cursor.fetchone()
        conn.close()
        
        if existing_profile:
            await update.message.reply_text(
                "У вас уже есть активная анкета!",
                reply_markup=self.get_main_menu_keyboard()
            )
            return
        
        self.user_states[user_id] = {'step': 'waiting_name'}
        await update.message.reply_text("👤 Введите ваше имя (как вас будут видеть другие пользователи):")

    async def handle_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ввода имени"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_states or self.user_states[user_id]['step'] != 'waiting_name':
            return
        
        name = update.message.text.strip()
        
        if len(name) < 2:
            await update.message.reply_text("Имя должно содержать минимум 2 символа. Попробуйте снова:")
            return
        
        if len(name) > 50:
            await update.message.reply_text("Имя слишком длинное. Максимум 50 символов. Попробуйте снова:")
            return
        
        self.user_states[user_id]['name'] = name
        self.user_states[user_id]['step'] = 'waiting_photo'
        await update.message.reply_text(f"✅ Имя сохранено: {name}\n\n📸 Теперь пришлите ваше фото для анкеты:")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик фотографий"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_states or self.user_states[user_id]['step'] != 'waiting_photo':
            return
        
        photo_file = await update.message.photo[-1].get_file()
        self.user_states[user_id]['photo_id'] = photo_file.file_id
        self.user_states[user_id]['step'] = 'waiting_gender'
        
        keyboard = [
            [
                InlineKeyboardButton("👨 Мужской", callback_data="gender_male"),
                InlineKeyboardButton("👩 Женский", callback_data="gender_female")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text("Выберите ваш пол:", reply_markup=reply_markup)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if user_id not in self.user_states:
            return
            
        if query.data.startswith('gender_'):
            gender = query.data.split('_')[1]
            self.user_states[user_id]['gender'] = gender
            self.user_states[user_id]['step'] = 'waiting_age'
            await query.edit_message_text("📅 Введите ваш возраст:")
            
        elif query.data.startswith('faculty_'):
            faculty_code = query.data.split('_')[1]
            faculty_name = FACULTIES.get(faculty_code, faculty_code)
            self.user_states[user_id]['faculty'] = faculty_name
            self.user_states[user_id]['step'] = 'waiting_bio'
            await query.edit_message_text(f"✅ Выбран факультет: {faculty_name}\n\n✏️ Теперь напишите информацию о себе (максимум 500 символов):")

    async def handle_age(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ввода возраста"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_states or self.user_states[user_id]['step'] != 'waiting_age':
            return
        
        try:
            age = int(update.message.text)
            if age < 16 or age > 100:
                await update.message.reply_text("Пожалуйста, введите реальный возраст (16-100):")
                return
                
            self.user_states[user_id]['age'] = age
            self.user_states[user_id]['step'] = 'waiting_faculty'
            
            await update.message.reply_text(
                "🎓 Выберите ваш факультет:",
                reply_markup=self.get_faculty_keyboard()
            )
            
        except ValueError:
            await update.message.reply_text("Пожалуйста, введите число:")

    async def handle_bio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ввода информации о себе"""
        user_id = update.effective_user.id
        bio = update.message.text
        
        if user_id not in self.user_states or self.user_states[user_id]['step'] != 'waiting_bio':
            return
        
        if len(bio) > 500:
            await update.message.reply_text("Слишком длинное описание! Максимум 500 символов:")
            return
        
        # Сохраняем анкету
        profile_data = self.user_states[user_id]
        
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO profiles (user_id, name, photo_id, gender, faculty, age, bio)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, 
            profile_data['name'],
            profile_data['photo_id'], 
            profile_data['gender'], 
            profile_data['faculty'], 
            profile_data['age'], 
            bio
        ))
        conn.commit()
        conn.close()
        
        # Очищаем состояние
        del self.user_states[user_id]
        
        await update.message.reply_text(
            "✅ Ваша анкета успешно создана!\n\n"
            "Теперь вы можете искать других пользователей.",
            reply_markup=self.get_main_menu_keyboard()
        )

    async def find_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Поиск случайной анкеты"""
        user_id = update.effective_user.id
        
        # Проверяем, есть ли анкета у пользователя
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM profiles WHERE user_id = ? AND is_active = TRUE', (user_id,))
        user_profile = cursor.fetchone()
        
        if not user_profile:
            await update.message.reply_text(
                "Сначала создайте свою анкету!",
                reply_markup=self.get_main_menu_keyboard()
            )
            conn.close()
            return
        
        # Ищем случайную анкету (кроме своей и уже оцененных)
        cursor.execute('''
            SELECT p.*, u.username 
            FROM profiles p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.user_id != ? 
            AND p.is_active = TRUE 
            AND p.profile_id NOT IN (
                SELECT to_profile_id FROM likes WHERE from_user_id = ?
            )
            ORDER BY RANDOM() LIMIT 1
        ''', (user_id, user_id))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            await update.message.reply_text(
                "😔 Вы просмотрели все анкеты!\n"
                "Попробуйте позже или настройки могут измениться.",
                reply_markup=self.get_main_menu_keyboard()
            )
            return
        
        # Распаковываем результат
        (profile_id, profile_user_id, name, photo_id, gender, 
         faculty, age, bio, is_active, created_at, username) = result
        
        gender_emoji = "👨" if gender == "male" else "👩"
        display_name = name or "Пользователь"
        
        caption = (
            f"{gender_emoji} {display_name}\n"
            f"🎓 Факультет: {faculty}\n"
            f"📅 Возраст: {age}\n"
            f"📝 О себе: {bio}"
        )
        
        # Сохраняем текущий профиль в контексте
        context.user_data['current_profile'] = {
            'profile_id': profile_id,
            'user_id': profile_user_id,
            'username': username
        }
        
        # Только кнопки лайк/дизлайк (без кнопки "следующая")
        keyboard = [
            [
                InlineKeyboardButton("❤️ Лайк", callback_data="like"),
                InlineKeyboardButton("👎 Дизлайк", callback_data="dislike")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_photo(
            photo=photo_id,
            caption=caption,
            reply_markup=reply_markup
        )

    async def handle_like(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик лайков/дизлайков"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        action = query.data
        
        current_profile = context.user_data.get('current_profile')
        if not current_profile:
            await query.edit_message_text("Произошла ошибка. Попробуйте снова.")
            return
        
        profile_id = current_profile['profile_id']
        profile_user_id = current_profile['user_id']
        username = current_profile['username']
        
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        if action == 'like':
            # Сохраняем лайк
            cursor.execute('''
                INSERT OR REPLACE INTO likes (from_user_id, to_profile_id, is_like)
                VALUES (?, ?, ?)
            ''', (user_id, profile_id, True))
            
            conn.commit()
            
            # Проверяем, взаимный ли это лайк
            cursor.execute('''
                SELECT 1 FROM likes 
                WHERE from_user_id = ? AND to_profile_id = ? AND is_like = TRUE
            ''', (profile_user_id, profile_id))
            
            is_mutual = cursor.fetchone()
            
            if is_mutual:
                # Взаимный лайк - показываем ссылку
                if username:
                    message_text = (
                        f"💝 Это взаимный лайк!\n\n"
                        f"Вы можете написать пользователю: @{username}\n\n"
                        f"Перейти в диалог: https://t.me/{username}"
                    )
                else:
                    # Если у пользователя нет username, используем его ID
                    message_text = (
                        f"💝 Это взаимный лайк!\n\n"
                        f"ID пользователя: {profile_user_id}\n"
                        f"Чтобы написать, скопируйте этот ID и используйте поиск в Telegram"
                    )
            else:
                # Не взаимный лайк
                message_text = "❤️ Вы поставили лайк!"
                
                if username:
                    message_text += f"\n\nСсылка на пользователя: @{username}"
                    message_text += f"\nhttps://t.me/{username}"
                
            await query.edit_message_text(message_text)
            
            # После лайка сразу показываем следующую анкету
            await self.show_next_profile(query, context)
                
        elif action == 'dislike':
            # Сохраняем дизлайк
            cursor.execute('''
                INSERT OR REPLACE INTO likes (from_user_id, to_profile_id, is_like)
                VALUES (?, ?, ?)
            ''', (user_id, profile_id, False))
            
            conn.commit()
            conn.close()
            
            await query.edit_message_text("👎 Вы поставили дизлайк")
            
            # После дизлайка сразу показываем следующую анкету
            await self.show_next_profile(query, context)

    async def show_next_profile(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Показать следующую анкету после действия"""
        user_id = query.from_user.id
        
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Ищем случайную анкету (кроме своей и уже оцененных)
        cursor.execute('''
            SELECT p.*, u.username 
            FROM profiles p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.user_id != ? 
            AND p.is_active = TRUE 
            AND p.profile_id NOT IN (
                SELECT to_profile_id FROM likes WHERE from_user_id = ?
            )
            ORDER BY RANDOM() LIMIT 1
        ''', (user_id, user_id))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            await query.message.reply_text(
                "😔 Вы просмотрели все доступные анкеты!\n"
                "Возвращайтесь позже, когда появятся новые анкеты.",
                reply_markup=self.get_main_menu_keyboard()
            )
            return
        
        # Распаковываем результат
        (profile_id, profile_user_id, name, photo_id, gender, 
         faculty, age, bio, is_active, created_at, username) = result
        
        gender_emoji = "👨" if gender == "male" else "👩"
        display_name = name or "Пользователь"
        
        caption = (
            f"{gender_emoji} {display_name}\n"
            f"🎓 Факультет: {faculty}\n"
            f"📅 Возраст: {age}\n"
            f"📝 О себе: {bio}"
        )
        
        # Сохраняем текущий профиль в контексте
        context.user_data['current_profile'] = {
            'profile_id': profile_id,
            'user_id': profile_user_id,
            'username': username
        }
        
        # Только кнопки лайк/дизлайк
        keyboard = [
            [
                InlineKeyboardButton("❤️ Лайк", callback_data="like"),
                InlineKeyboardButton("👎 Дизлайк", callback_data="dislike")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_photo(
            photo=photo_id,
            caption=caption,
            reply_markup=reply_markup
        )

    async def show_matches(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать мэтчи пользователя"""
        user_id = update.effective_user.id
        
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Находим взаимные лайки
        cursor.execute('''
            SELECT p.name, u.username, p.faculty, p.bio, u.user_id
            FROM likes l1
            JOIN likes l2 ON l1.to_profile_id = l2.from_user_id
            JOIN profiles p ON l2.from_user_id = p.user_id
            JOIN users u ON p.user_id = u.user_id
            WHERE l1.from_user_id = ? 
            AND l2.to_profile_id = l1.from_user_id
            AND l1.is_like = TRUE 
            AND l2.is_like = TRUE
        ''', (user_id,))
        
        matches = cursor.fetchall()
        conn.close()
        
        if not matches:
            await update.message.reply_text(
                "😔 У вас пока нет мэтчей.\n"
                "Продолжайте ставить лайки!",
                reply_markup=self.get_main_menu_keyboard()
            )
            return
        
        match_text = "💝 Ваши мэтчи:\n\n"
        for match in matches:
            name, username, faculty, bio, match_user_id = match
            display_name = name or username or "Пользователь"
            
            match_text += f"👤 {display_name}\n"
            match_text += f"🎓 Факультет: {faculty}\n"
            match_text += f"📝 {bio}\n"
            
            if username:
                match_text += f"💬 Написать: @{username}\n"
                match_text += f"🔗 Ссылка: https://t.me/{username}\n"
            else:
                match_text += f"🆔 ID пользователя: {match_user_id}\n"
            
            match_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        await update.message.reply_text(
            match_text,
            reply_markup=self.get_main_menu_keyboard()
        )

    async def show_my_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать анкету пользователя"""
        user_id = update.effective_user.id
        
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM profiles WHERE user_id = ? AND is_active = TRUE', (user_id,))
        profile = cursor.fetchone()
        conn.close()
        
        if not profile:
            await update.message.reply_text(
                "У вас еще нет анкеты!",
                reply_markup=self.get_main_menu_keyboard()
            )
            return
        
        profile_id, user_id, name, photo_id, gender, faculty, age, bio, is_active, created_at = profile
        gender_text = "Мужской" if gender == "male" else "Женский"
        
        caption = (
            f"👤 Ваша анкета:\n\n"
            f"📛 Имя: {name}\n"
            f"🎓 Факультет: {faculty}\n"
            f"👫 Пол: {gender_text}\n"
            f"📅 Возраст: {age}\n"
            f"📝 О себе: {bio}"
        )
        
        await update.message.reply_photo(
            photo=photo_id,
            caption=caption,
            reply_markup=self.get_main_menu_keyboard()
        )

    async def delete_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаление анкеты"""
        user_id = update.effective_user.id
        
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('UPDATE profiles SET is_active = FALSE WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            "✅ Ваша анкета удалена!",
            reply_markup=self.get_main_menu_keyboard()
        )

    def run(self):
        """Запуск бота"""
        application = Application.builder().token(BOT_TOKEN).build()

        # Обработчики команд
        application.add_handler(CommandHandler("start", self.start))
        
        # Обработчики сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        
        # Обработчики callback-запросов
        application.add_handler(CallbackQueryHandler(self.handle_callback, pattern="^gender_"))
        application.add_handler(CallbackQueryHandler(self.handle_callback, pattern="^faculty_"))
        application.add_handler(CallbackQueryHandler(self.handle_like, pattern="^(like|dislike)$"))

        print("🤖 Бот запускается...")
        print("✅ База данных готова")
        print("🚀 Бот работает! Напишите /start в Telegram")
        
        application.run_polling()

if __name__ == "__main__":
    bot = DatingBot()
    bot.run()
