import os
import logging
import requests
import base64
import json
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

def analyze_image_with_roboflow(image_path, api_key):
    """Анализирует изображение через Roboflow API"""
    try:
        # Читаем и кодируем изображение в base64
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
            base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Формируем запрос согласно документации Roboflow
        url = "https://serverless.roboflow.com/kalori-lsshy/workflows/detect-count-and-visualize"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "api_key": api_key,
            "inputs": {
                "image": {
                    "type": "base64",
                    "value": base64_image
                }
            }
        }
        
        logger.info(f"Отправляю запрос к Roboflow: {url}")
        
        # Отправляем запрос
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        logger.info(f"Статус ответа: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Успешный ответ от Roboflow")
            return result
        else:
            logger.error(f"Ошибка API: {response.status_code}")
            logger.error(f"Текст ошибки: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("Таймаут при запросе к Roboflow")
        return None
    except Exception as e:
        logger.error(f"Ошибка при анализе изображения: {e}")
        return None

async def handle_photo(update: Update, context: CallbackContext) -> None:
    """Обработчик фото"""
    image_path = None
    output_image_path = None
    
    try:
        user = update.message.from_user
        logger.info(f"Пользователь {user.first_name} отправил фото")
        
        await update.message.reply_text("🔍 Анализирую изображение...")
        
        # Скачиваем фото
        photo_file = await update.message.photo[-1].get_file()
        image_path = f"temp_{user.id}.jpg"
        await photo_file.download_to_drive(image_path)
        
        logger.info(f"Фото скачано: {image_path}")
        
        # Анализируем изображение через Roboflow
        result = analyze_image_with_roboflow(image_path, ROBOFLOW_API_KEY)
        
        if result:
            logger.info(f"Получен результат от Roboflow")
            
            # Обрабатываем результат
            # Результат - это список с одним словарем
            if isinstance(result, list) and len(result) > 0:
                data = result[0]
                
                # Извлекаем количество объектов
                count_objects = data.get("count_objects", 0)
                
                # Рассчитываем примерную калорийность
                # Поскольку мы не знаем типы объектов, используем приблизительный расчет
                estimated_calories = count_objects * 150  # Среднее значение ~150 ккал на объект
                
                # Формируем текстовый ответ
                text_response = (
                    f"📊 Результаты анализа:\n"
                    f"• Обнаружено объектов: {count_objects}\n"
                    f"• Примерная калорийность: {estimated_calories} ккал\n\n"
                    f"💡 Совет: Для более точного расчета калорий "
                    f"настройте workflow для определения типов еды."
                )
                
                # Проверяем наличие обработанного изображения
                if "output_image" in data:
                    output_image = data["output_image"]
                    if output_image.get("type") == "base64":
                        base64_value = output_image.get("value", "")
                        
                        if base64_value:
                            # Декодируем base64 изображение
                            try:
                                # Убедимся, что строка base64 корректна
                                # Иногда нужно добавить padding
                                missing_padding = len(base64_value) % 4
                                if missing_padding:
                                    base64_value += '=' * (4 - missing_padding)
                                
                                image_data = base64.b64decode(base64_value)
                                
                                # Сохраняем декодированное изображение
                                output_image_path = f"output_{user.id}.jpg"
                                with open(output_image_path, "wb") as f:
                                    f.write(image_data)
                                
                                logger.info(f"Обработанное изображение сохранено: {output_image_path}")
                                
                                # Отправляем обработанное изображение с подписью
                                with open(output_image_path, "rb") as photo_file:
                                    await update.message.reply_photo(
                                        photo=photo_file,
                                        caption=text_response
                                    )
                                
                            except Exception as e:
                                logger.error(f"Ошибка при декодировании изображения: {e}")
                                await update.message.reply_text(text_response)
                        else:
                            await update.message.reply_text(text_response)
                    else:
                        await update.message.reply_text(text_response)
                else:
                    await update.message.reply_text(text_response)
            else:
                await update.message.reply_text(
                    "⚠️ Неожиданный формат ответа от Roboflow.\n"
                    "Попробуйте еще раз или проверьте настройки workflow."
                )
        else:
            await update.message.reply_text(
                "⚠️ Не удалось получить ответ от сервиса анализа.\n"
                "Попробуйте еще раз или свяжитесь с разработчиком."
            )
            
    except Exception as e:
        logger.error(f"Ошибка при обработке фото: {e}", exc_info=True)
        await update.message.reply_text(
            f"⚠️ Произошла ошибка при обработке фото.\n"
            "Попробуйте еще раз или свяжитесь с разработчиком."
        )
    
    finally:
        # Удаляем временные файлы
        for file_path in [image_path, output_image_path]:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Временный файл удален: {file_path}")
                except Exception as e:
                    logger.error(f"Ошибка при удалении файла {file_path}: {e}")

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
