import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from inference_sdk import InferenceHTTPClient
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
    raise ValueError("❌ TELEGRAM_BOT_TOKEN не установлен! Добавьте его в переменные окружения Railway.")
if not ROBOFLOW_API_KEY:
    raise ValueError("❌ ROBOFLOW_API_KEY не установлен! Добавьте его в переменные окружения Railway.")

# Инициализация клиента Roboflow
client = InferenceHTTPClient(
    api_url="https://serverless.roboflow.com",
    api_key=ROBOFLOW_API_KEY
)

async def start(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /start"""
    await update.message.reply_text(
        "🍏 Привет! Я бот для подсчета калорий.\n"
        "Просто отправь мне фото еды, и я определю:\n"
        "• Количество объектов\n"
        "• Примерную калорийность\n\n"
        "Отправь фото для анализа!"
    )

async def handle_photo(update: Update, context: CallbackContext) -> None:
    """Обработчик фото"""
    user = update.message.from_user
    logger.info(f"Пользователь {user.first_name} отправил фото")
    
    await update.message.reply_text("🔍 Анализирую изображение...")
    
    try:
        # Скачиваем фото
        photo_file = await update.message.photo[-1].get_file()
        image_path = f"temp_{user.id}.jpg"
        await photo_file.download_to_drive(image_path)
        
        # Отправляем в Roboflow
        result = client.run_workflow(
            workspace_name="kalori-lsshy",
            workflow_id="detect-count-and-visualize",
            images={
                "image": image_path
            },
            use_cache=True
        )
        
        # Обработка результата
        # ВАЖНО: адаптируйте под реальную структуру ответа от вашего workflow
        if result and "predictions" in result:
            predictions = result["predictions"]
            
            # Считаем общее количество
            total_count = len(predictions)
            
            # Примерная калорийность (нужно адаптировать)
            # Здесь предполагается, что каждый объект ~100 калорий
            total_calories = total_count * 100
            
            response = (
                f"📊 Результаты анализа:\n"
                f"• Обнаружено объектов: {total_count}\n"
                f"• Примерная калорийность: {total_calories} ккал\n\n"
                f"🔎 Детали:\n"
            )
            
            for i, pred in enumerate(predictions, 1):
                label = pred.get("class", "объект")
                confidence = pred.get("confidence", 0.0) * 100
                response += f"{i}. {label} ({confidence:.1f}%)\n"
                
            await update.message.reply_text(response)
            
            # Отправляем обработанное изображение, если есть
            if "image" in result:
                # Здесь можно сохранить и отправить обработанное изображение
                pass
                
        else:
            await update.message.reply_text(
                "🤔 Не удалось определить объекты на фото.\n"
                "Попробуй другое изображение с более четкой едой."
            )
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text(
            "⚠️ Произошла ошибка при обработке изображения.\n"
            "Попробуй еще раз или свяжись с разработчиком."
        )
    
    finally:
        # Удаляем временный файл
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
        except:
            pass

async def help_command(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /help"""
    await update.message.reply_text(
        "📋 Доступные команды:\n"
        "/start - Начать работу\n"
        "/help - Показать справку\n\n"
        "Просто отправьте фото еды для анализа калорий!"
    )

def main() -> None:
    """Запуск бота"""
    try:
        # Создаем приложение
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Регистрируем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        
        # Логируем запуск
        logger.info("🚀 Бот запускается...")
        print("=" * 50)
        print("✅ Бот успешно запущен!")
        print(f"🤖 Используется токен: {TELEGRAM_BOT_TOKEN[:10]}...")
        print("=" * 50)
        
        # Запускаем бота
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске: {e}")
        raise

if __name__ == '__main__':
    main()
