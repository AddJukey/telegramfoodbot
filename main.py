import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from inference_sdk import InferenceHTTPClient
import logging

# Включите логирование для отладки
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация Roboflow
ROBOFLOW_API_KEY = "pxdm5gsSa9zxNzhvq4oX"  # Замените на ваш ключ
WORKSPACE_NAME = "kalori-lsshy"
WORKFLOW_ID = "detect-count-and-visualize"

# Инициализация клиента Roboflow
client = InferenceHTTPClient(
    api_url="https://serverless.roboflow.com",
    api_key=ROBOFLOW_API_KEY
)

# Команда /start
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "Привет! Отправь мне фото еды, и я определю количество объектов и подсчитаю калории."
    )

# Обработка фото
async def handle_photo(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    photo_file = await update.message.photo[-1].get_file()
    
    # Сохраняем фото временно
    image_path = f"temp_{user.id}.jpg"
    await photo_file.download_to_drive(image_path)
    
    await update.message.reply_text("🔍 Анализирую изображение...")

    try:
        # Отправляем изображение в Roboflow
        result = client.run_workflow(
            workspace_name=WORKSPACE_NAME,
            workflow_id=WORKFLOW_ID,
            images={
                "image": image_path
            },
            use_cache=True
        )

        # Извлекаем данные из результата
        # Структура ответа зависит от вашего workflow. Пример:
        predictions = result.get("predictions", [])
        
        if predictions:
            total_objects = len(predictions)
            # Пример: если модель возвращает калории для каждого объекта
            total_calories = sum([pred.get("calories", 0) for pred in predictions])
            
            response_text = (
                f"🍽️ На фото обнаружено объектов: {total_objects}\n"
                f"🔥 Примерная сумма калорий: {total_calories} ккал\n\n"
                "Детали:\n"
            )
            
            for i, pred in enumerate(predictions, 1):
                label = pred.get("class", "Неизвестно")
                confidence = pred.get("confidence", 0)
                calories = pred.get("calories", "?")
                response_text += f"{i}. {label} (уверенность: {confidence:.2f}) — {calories} ккал\n"
                
        else:
            response_text = "❌ На фото не удалось распознать объекты еды."

        await update.message.reply_text(response_text)

    except Exception as e:
        logger.error(f"Ошибка при обработке изображения: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при анализе изображения.")

    finally:
        # Удаляем временный файл
        if os.path.exists(image_path):
            os.remove(image_path)

# Основная функция
def main() -> None:
    # Замените 'YOUR_TELEGRAM_BOT_TOKEN' на токен вашего бота
    application = Application.builder().token("7810084882:AAEvk7cJLNBTu6SvXsWM-2gZdsjduraSZNc").build()

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
