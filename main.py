import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from inference_sdk import InferenceHTTPClient  # ИСПОЛЬЗУЕМ inference_sdk
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

# Инициализация клиента Roboflow (ОРИГИНАЛЬНЫЙ КОД из Roboflow)
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
        
        # ОТПРАВЛЯЕМ В ROB0FLOW (ОРИГИНАЛЬНЫЙ КОД)
        result = client.run_workflow(
            workspace_name="kalori-lsshy",
            workflow_id="detect-count-and-visualize",
            images={
                "image": image_path
            },
            use_cache=True
        )
        
        logger.info(f"Получен ответ от Roboflow: {result}")
        
        # Обработка результата
        # ВАЖНО: адаптируйте под реальную структуру ответа от вашего workflow
        if result:
            # Попробуем разные возможные структуры ответа
            predictions = result.get("predictions", [])
            if not predictions and isinstance(result, list):
                predictions = result
            
            if predictions:
                total_count = len(predictions)
                
                # Пробуем получить калории из ответа
                total_calories = 0
                for pred in predictions:
                    if isinstance(pred, dict):
                        calories = pred.get("calories", 0)
                        if isinstance(calories, (int, float)):
                            total_calories += calories
                        else:
                            total_calories += 100  # Значение по умолчанию
                
                # Если калории не найдены, используем приблизительный расчет
                if total_calories == 0:
                    total_calories = total_count * 100
                
                response = (
                    f"📊 Результаты анализа:\n"
                    f"• Обнаружено объектов: {total_count}\n"
                    f"• Примерная калорийность: {total_calories} ккал\n\n"
                )
                
                # Добавляем детали по объектам
                details = []
                for i, pred in enumerate(predictions[:10], 1):  # Ограничим 10 объектами
                    if isinstance(pred, dict):
                        label = pred.get("class", pred.get("label", pred.get("name", "объект")))
                        confidence = pred.get("confidence", pred.get("score", 0.0))
                        if isinstance(confidence, (int, float)):
                            confidence_percent = confidence * 100
                            details.append(f"{i}. {label} ({confidence_percent:.1f}%)")
                        else:
                            details.append(f"{i}. {label}")
                    else:
                        details.append(f"{i}. Объект")
                
                if details:
                    response += "🔎 Обнаруженные объекты:\n" + "\n".join(details)
                else:
                    response += "ℹ️ Детали объектов недоступны"
                    
                await update.message.reply_text(response)
            else:
                await update.message.reply_text(
                    "🤔 Не удалось определить объекты на фото.\n"
                    "Попробуй другое изображение с более четкой едой."
                )
        else:
            await update.message.reply_text(
                "⚠️ Получен пустой ответ от сервиса анализа.\n"
                "Попробуй еще раз."
            )
            
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
