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
        
        self.user_states[user_id] = {'step': 'waiting_photo'}
        await update.message.reply_text("📸 Пришлите ваше фото для анкеты:")

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
        
        if query.data.startswith('gender_'):
            gender = query.data.split('_')[1]
            self.user_states[user_id]['gender'] = gender
            self.user_states[user_id]['step'] = 'waiting_age'
            await query.edit_message_text("📅 Введите ваш возраст:")

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
            self.user_states[user_id]['step'] = 'waiting_bio'
            
            await update.message.reply_text("✏️ Напишите информацию о себе (максимум 500 символов):")
            
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
            INSERT INTO profiles (user_id, photo_id, gender, faculty, age, bio)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, profile_data['photo_id'], profile_data['gender'], "Не указан", profile_data['age'], bio))
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
        
        # Ищем случайную анкету (кроме своей)
        cursor.execute('''
            SELECT * FROM profiles 
            WHERE user_id != ? AND is_active = TRUE 
            ORDER BY RANDOM() LIMIT 1
        ''', (user_id,))
        profile = cursor.fetchone()
        conn.close()
        
        if not profile:
            await update.message.reply_text(
                "😔 Пока нет анкет для просмотра.\n"
                "Попробуйте позже!",
                reply_markup=self.get_main_menu_keyboard()
            )
            return
        
        profile_id, profile_user_id, photo_id, gender, faculty, age, bio, is_active, created_at = profile
        
        # Получаем информацию о пользователе
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT username, first_name FROM users WHERE user_id = ?', (profile_user_id,))
        user_info = cursor.fetchone()
        conn.close()
        
        username, first_name = user_info if user_info else (None, None)
        
        gender_emoji = "👨" if gender == "male" else "👩"
        display_name = first_name or username or "Пользователь"
        
        caption = (
            f"{gender_emoji} {display_name}\n"
            f"🎓 Факультет: {faculty}\n"
            f"📅 Возраст: {age}\n"
            f"📝 О себе: {bio}"
        )
        
        # Сохраняем текущий профиль в контексте
        context.user_data['current_profile'] = profile_id
        
        keyboard = [
            [
                InlineKeyboardButton("❤️", callback_data="like"),
                InlineKeyboardButton("👎", callback_data="dislike")
            ],
            [InlineKeyboardButton("⏭️ Следующая анкета", callback_data="skip")]
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
        current_profile_id = context.user_data.get('current_profile')
        
        if not current_profile_id:
            await query.edit_message_text("Произошла ошибка. Попробуйте снова.")
            return
        
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        if action == 'like':
            # Сохраняем лайк
            cursor.execute('''
                INSERT OR REPLACE INTO likes (from_user_id, to_profile_id, is_like)
                VALUES (?, ?, ?)
            ''', (user_id, current_profile_id, True))
            
            await query.edit_message_text("❤️ Вы поставили лайк!")
                
        elif action == 'dislike':
            # Сохраняем дизлайк
            cursor.execute('''
                INSERT OR REPLACE INTO likes (from_user_id, to_profile_id, is_like)
                VALUES (?, ?, ?)
            ''', (user_id, current_profile_id, False))
            await query.edit_message_text("👎 Вы поставили дизлайк")
        
        conn.commit()
        conn.close()
        
        # Показываем следующую анкету
        await self.find_profile_by_message(query, context)

    async def find_profile_by_message(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Показать следующую анкету после действия"""
        user_id = query.from_user.id
        
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Ищем случайную анкету (кроме своей)
        cursor.execute('''
            SELECT * FROM profiles 
            WHERE user_id != ? AND is_active = TRUE 
            ORDER BY RANDOM() LIMIT 1
        ''', (user_id,))
        profile = cursor.fetchone()
        
        if not profile:
            await query.message.reply_text(
                "😔 Пока нет новых анкет для просмотра.\n"
                "Попробуйте позже!",
                reply_markup=self.get_main_menu_keyboard()
            )
            conn.close()
            return
        
        profile_id, profile_user_id, photo_id, gender, faculty, age, bio, is_active, created_at = profile
        
        # Получаем информацию о пользователе
        cursor.execute('SELECT username, first_name FROM users WHERE user_id = ?', (profile_user_id,))
        user_info = cursor.fetchone()
        conn.close()
        
        username, first_name = user_info if user_info else (None, None)
        
        gender_emoji = "👨" if gender == "male" else "👩"
        display_name = first_name or username or "Пользователь"
        
        caption = (
            f"{gender_emoji} {display_name}\n"
            f"🎓 Факультет: {faculty}\n"
            f"📅 Возраст: {age}\n"
            f"📝 О себе: {bio}"
        )
        
        # Сохраняем текущий профиль в контексте
        context.user_data['current_profile'] = profile_id
        
        keyboard = [
            [
                InlineKeyboardButton("❤️", callback_data="like"),
                InlineKeyboardButton("👎", callback_data="dislike")
            ],
            [InlineKeyboardButton("⏭️ Следующая анкета", callback_data="skip")]
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
            SELECT u.username, u.first_name, p.bio 
            FROM likes l1
            JOIN likes l2 ON l1.to_profile_id = l2.to_profile_id
            JOIN profiles p ON l2.from_user_id = p.user_id
            JOIN users u ON p.user_id = u.user_id
            WHERE l1.from_user_id = ? AND l2.from_user_id = p.user_id
            AND l1.is_like = TRUE AND l2.is_like = TRUE
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
            username, first_name, bio = match
            name = first_name or username or "Пользователь"
            match_text += f"👤 {name}\n"
            match_text += f"📝 {bio}\n"
            match_text += f"💬 Написать: @{username}\n\n" if username else "\n"
        
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
        
        profile_id, user_id, photo_id, gender, faculty, age, bio, is_active, created_at = profile
        gender_text = "Мужской" if gender == "male" else "Женский"
        
        caption = (
            f"👤 Ваша анкета:\n\n"
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
        application.add_handler(CallbackQueryHandler(self.handle_like, pattern="^(like|dislike|skip)$"))
        
        # Обработчики для создания анкеты
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_age), group=1)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_bio), group=2)

        print("🤖 Бот запускается...")
        print("✅ База данных готова")
        print("🚀 Бот работает! Напишите /start в Telegram")
        
        application.run_polling()

if __name__ == "__main__":
    bot = DatingBot()
    bot.run()
