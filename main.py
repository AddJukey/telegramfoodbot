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
            logger.info(f"Успешный ответ от Roboflow. Структура ответа: {type(result)}")
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
    
    try:
        user = update.message.from_user
        logger.info(f"Пользователь {user.first_name} отправил фото")
        
        await update.message.reply_text("🔍 Анализирую изображение...")
        
        # Скачиваем фото (берем фото среднего качества для экономии трафика)
        photo_file = await update.message.photo[-1].get_file()
        image_path = f"temp_{user.id}.jpg"
        await photo_file.download_to_drive(image_path)
        
        logger.info(f"Фото скачано: {image_path}, размер: {os.path.getsize(image_path)} байт")
        
        # Анализируем изображение через Roboflow
        result = analyze_image_with_roboflow(image_path, ROBOFLOW_API_KEY)
        
        if result:
            logger.info(f"Получен результат от Roboflow. Ключи: {result.keys() if isinstance(result, dict) else 'не dict'}")
            
            # Обработка результата - адаптируйте под ваш workflow!
            # В зависимости от структуры вашего workflow, данные могут быть в разных полях
            
            # Вариант 1: Если workflow возвращает предсказания напрямую
            if "predictions" in result:
                predictions = result["predictions"]
                await process_predictions(update, predictions)
            
            # Вариант 2: Если workflow возвращает данные в другом формате
            elif "outputs" in result:
                outputs = result["outputs"]
                await process_workflow_outputs(update, outputs)
            
            # Вариант 3: Простая проверка наличия любых данных
            elif result:
                await process_generic_result(update, result)
            
            else:
                await update.message.reply_text(
                    "🤔 Не удалось определить объекты на фото.\n"
                    "Попробуйте другое изображение с более четкой едой."
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
        # Удаляем временный файл
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                logger.info(f"Временный файл удален: {image_path}")
            except Exception as e:
                logger.error(f"Ошибка при удалении файла: {e}")

async def process_predictions(update, predictions):
    """Обработка предсказаний от модели"""
    if isinstance(predictions, list) and len(predictions) > 0:
        total_count = len(predictions)
        
        # Считаем примерную калорийность
        total_calories = 0
        details = []
        
        for i, pred in enumerate(predictions[:10], 1):  # Ограничим 10 объектами
            if isinstance(pred, dict):
                label = pred.get("class", pred.get("label", "объект"))
                confidence = pred.get("confidence", 0)
                
                # Примерные калории по типу объекта
                calories = estimate_calories_by_label(label)
                total_calories += calories
                
                if isinstance(confidence, (int, float)):
                    details.append(f"{i}. {label} ({confidence:.1%}) - ~{calories} ккал")
                else:
                    details.append(f"{i}. {label} - ~{calories} ккал")
        
        # Если не нашли калорий в предсказаниях, используем приблизительный расчет
        if total_calories == 0:
            total_calories = total_count * 100  # 100 ккал на объект по умолчанию
        
        response = (
            f"📊 Результаты анализа:\n"
            f"• Обнаружено объектов: {total_count}\n"
            f"• Примерная калорийность: {total_calories} ккал\n\n"
        )
        
        if details:
            response += "🔎 Обнаруженные объекты:\n" + "\n".join(details)
        
        await update.message.reply_text(response)
    else:
        await update.message.reply_text("🤔 На фото не обнаружено объектов еды.")

async def process_workflow_outputs(update, outputs):
    """Обработка выходных данных workflow"""
    # Адаптируйте эту функцию под структуру вашего workflow
    # Например, если workflow возвращает изображение с аннотациями и данные
    
    # Простой вывод JSON для отладки
    output_str = json.dumps(outputs, ensure_ascii=False, indent=2)[:1000]  # Ограничим длину
    
    await update.message.reply_text(
        f"📋 Получены данные от workflow:\n"
        f"```json\n{output_str}\n```\n\n"
        f"Для настройки вывода проверьте структуру данных вашего workflow.",
        parse_mode='Markdown'
    )

async def process_generic_result(update, result):
    """Обработка общего результата"""
    # Для отладки: покажем структуру ответа
    if isinstance(result, dict):
        result_keys = list(result.keys())
        await update.message.reply_text(
            f"📋 Получен ответ от Roboflow.\n"
            f"Ключи в ответе: {', '.join(result_keys)}\n\n"
            f"Для настройки вывода адаптируйте код под структуру вашего workflow."
        )
    else:
        await update.message.reply_text(
            f"📋 Получен ответ от Roboflow.\n"
            f"Тип ответа: {type(result)}\n\n"
            f"Для настройки вывода адаптируйте код под структуру вашего workflow."
        )

def estimate_calories_by_label(label):
    """Оценка калорийности по метке объекта"""
    # Добавьте свои правила для определения калорий
    label_lower = label.lower()
    
    calorie_map = {
        "apple": 95, "banana": 105, "orange": 62, "bread": 79, "cheese": 113,
        "egg": 78, "chicken": 335, "fish": 206, "rice": 130, "pasta": 157,
        "potato": 163, "tomato": 22, "cucumber": 16, "carrot": 41, "broccoli": 55,
        "pizza": 285, "burger": 354, "fries": 365, "salad": 150, "soup": 100,
        "cake": 235, "chocolate": 546, "ice cream": 207, "yogurt": 149, "milk": 103
    }
    
    # Поиск по частичному совпадению
    for key, calories in calorie_map.items():
        if key in label_lower:
            return calories
    
    # Если не нашли, возвращаем среднее значение
    return 100

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
