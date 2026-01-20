import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY")

# Проверка токенов
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN не установлен! Добавьте его в Railway Variables.")
if not ROBOFLOW_API_KEY:
    raise ValueError("❌ ROBOFLOW_API_KEY не установлен! Добавьте его в Railway Variables.")

print("=" * 50)
print("✅ Конфигурация загружена")
print(f"🤖 Токен бота: {TELEGRAM_BOT_TOKEN[:10]}...")
print(f"🔑 Ключ Roboflow: {ROBOFLOW_API_KEY[:10]}...")
print("=" * 50)

async def start(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /start"""
    await update.message.reply_text(
        "🍏 Привет! Я бот для подсчета калорий.\n"
        "Просто отправь мне фото еды, и я определю:\n"
        "• Количество объектов\n"
        "• Примерную калорийность\n\n"
        "Отправь фото для анализа!"
    )

async def help_command(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /help"""
    await update.message.reply_text(
        "📋 Доступные команды:\n"
        "/start - Начать работу\n"
        "/help - Показать справку\n\n"
        "Просто отправьте фото еды для анализа калорий!"
    )

async def handle_photo(update: Update, context: CallbackContext) -> None:
    """Обработчик фото"""
    try:
        user = update.message.from_user
        logger.info(f"Пользователь {user.first_name} отправил фото")
        
        await update.message.reply_text("🔍 Анализирую изображение...")
        
        # Скачиваем фото
        photo_file = await update.message.photo[-1].get_file()
        image_path = f"temp_{user.id}.jpg"
        await photo_file.download_to_drive(image_path)
        
        logger.info("Фото скачано, отправляю в Roboflow...")
        
        # 1. Прямой запрос к Roboflow API (самый простой способ)
        with open(image_path, 'rb') as image_file:
            files = {'file': image_file}
            headers = {'Authorization': f'Bearer {ROBOFLOW_API_KEY}'}
            
            # URL для workflow - АДАПТИРУЙТЕ ПОД СВОЙ WORKFLOW!
            # Получите правильный URL из интерфейса Roboflow
            response = requests.post(
                f'https://detect.roboflow.com/kalori-lsshy/detect-count-and-visualize?api_key={ROBOFLOW_API_KEY}',
                files=files,
                headers=headers
            )
        
        logger.info(f"Статус ответа от Roboflow: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Получен ответ от Roboflow: {result}")
            
            # Обработка результата
            # Структура ответа зависит от вашей модели
            predictions = result.get('predictions', [])
            
            if predictions:
                total_count = len(predictions)
                total_calories = total_count * 100  # Примерный расчет
                
                response_text = (
                    f"📊 Результаты анализа:\n"
                    f"• Обнаружено объектов: {total_count}\n"
                    f"• Примерная калорийность: {total_calories} ккал\n\n"
                )
                
                # Добавляем детали
                for i, pred in enumerate(predictions[:5], 1):
                    label = pred.get('class', 'объект')
                    confidence = pred.get('confidence', 0) * 100
                    response_text += f"{i}. {label} ({confidence:.1f}%)\n"
                
                await update.message.reply_text(response_text)
            else:
                await update.message.reply_text("🤔 На фото не обнаружено объектов еды.")
        else:
            logger.error(f"Ошибка API: {response.status_code}, {response.text}")
            await update.message.reply_text("⚠️ Ошибка при анализе изображения. Попробуйте еще раз.")
            
    except Exception as e:
        logger.error(f"Ошибка при обработке фото: {e}", exc_info=True)
        await update.message.reply_text(
            f"⚠️ Произошла ошибка: {str(e)[:100]}\n"
            "Попробуй еще раз или свяжись с разработчиком."
        )
    
    finally:
        # Удаляем временный файл
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
        except:
            pass

def main() -> None:
    """Запуск бота"""
    try:
        print("🚀 Запуск Telegram бота...")
        
        # Создаем приложение
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Регистрируем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        
        print("✅ Обработчики зарегистрированы")
        print("🤖 Бот запущен и ожидает сообщений...")
        print("=" * 50)
        
        # Запускаем бота
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске: {e}", exc_info=True)
        print(f"❌ Критическая ошибка: {e}")
        raise

if __name__ == '__main__':
    main()
