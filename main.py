import telebot
import requests
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


API_TOKEN = 'СЮДА_ТОКЕН_БОТА'

BITRIX_WEBHOOK = 'СЮДА_ВЕБХУК_БИТРИКСА'

bot = telebot.TeleBot(API_TOKEN)

# Временное хранение данных пользователя
user_data = {}
current_step = {}

# Функции для работы с Битрикс24
def upload_file_to_bitrix(file_url, file_name, folder_id=ПОМЕНЯТЬ): # Это id папки на Битрикс24
    try:
        # Скачиваем файл с серверов Telegram
        file_data = requests.get(file_url).content  # Содержимое файла
        file_size = len(file_data)  # Размер файла в байтах
        print(f"Файл успешно скачан. Размер: {file_size} байт.")  # Логируем размер
        if file_size > 10 * 1024 * 1024:  # Ограничение на 10 МБ
            print("Файл слишком большой.")
            return None
    except Exception as e:
        print("Ошибка при скачивании файла:", e)
        return None

    # Получаем URL для загрузки файла
    upload_response = requests.post(
        f"{BITRIX_WEBHOOK}disk.folder.uploadfile",
        data={'id': folder_id}  
    )
    upload_result = upload_response.json()
    print("Результат запроса на загрузку файла:", upload_result)  # Логируем ответ
    if 'result' in upload_result and 'uploadUrl' in upload_result['result']:
        upload_url = upload_result['result']['uploadUrl']
        print("URL для загрузки файла:", upload_url)
        # Загружаем файл на полученный URL с оригинальным именем
        files = {'file': (file_name, file_data)}
        upload_file_response = requests.post(upload_url, files=files)
        upload_file_result = upload_file_response.json()
        print("Результат загрузки файла:", upload_file_result)  # Логируем ответ
        if 'result' in upload_file_result and 'ID' in upload_file_result['result']:
            file_link = upload_file_result['result']['DOWNLOAD_URL']  # Получаем ссылку на файл
            print(f"Файл успешно загружен. Ссылка на файл: {file_link}")
            return file_link
        else:
            print("Ошибка загрузки файла:", upload_file_result)
            return None
    else:
        print("Ошибка при получении URL для загрузки файла:", upload_result)
        return None

def create_contact(data):
    contact_data = {
        "fields": {
            "NAME": data['name'],
            "PHONE": [{"VALUE": data['phone'], "VALUE_TYPE": "WORK"}]
        }
    }
    response = requests.post(f"{BITRIX_WEBHOOK}crm.contact.add.json", json=contact_data)
    return response.json().get("result")

def create_deal(data, contact_id, file_links):
    deal_data = {
        "fields": {
            "TITLE": f"Заявка от {data['name']}",
            "CONTACT_ID": contact_id,
            "УКАЗАТЬ_ID_ПОЛЯ": data.get('inn', ''),
            "УКАЗАТЬ_ID_ПОЛЯ": data.get('article', ''),
            "УКАЗАТЬ_ID_ПОЛЯ": data.get('date', ''),
            "УКАЗАТЬ_ID_ПОЛЯ": file_links  # Передаём массив ссылок
        }
    }
    print("Данные для создания сделки:", deal_data)
    response = requests.post(f"{BITRIX_WEBHOOK}crm.deal.add.json", json=deal_data)
    print("Ответ от API при создании сделки:", response.json())
    return response.json().get("result")

# Завершение обработки данных
def finalize_application(chat_id):
    data = user_data.get(chat_id, {})
    file_links = []
    # Проверяем, есть ли файлы
    if data.get('file') and data.get('file_name'):
        for file_url, file_name in zip(data['file'], data['file_name']):
            bitrix_link = upload_file_to_bitrix(file_url, file_name, folder_id=ПОМЕНЯТЬ) # Указываем то же id папки Битрикс24 что было ранее
            if bitrix_link:
                file_links.append(bitrix_link)
    else:
        print(f"Пользователь {chat_id} не загрузил файлы.")

    contact_id = create_contact(data)
    if not contact_id:
        bot.send_message(chat_id, "Ошибка при создании контакта. Попробуйте позже.")
        return

    response = create_deal(data, contact_id, file_links)
    if response:
        bot.send_message(chat_id, f"Ваше обращение передано ответственному юристу. Скоро мы с вами свяжемся.")
    else:
        bot.send_message(chat_id, "Ошибка при создании заявки.")

    # Очищаем данные после завершения
    user_data.pop(chat_id, None)
    current_step.pop(chat_id, None)

# Inline-кнопка "Пропустить"
def skip_button():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Пропустить", callback_data="skip"))
    return markup

# Inline-кнопка "Старт"
def start_button():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("СТАРТ", callback_data="start_survey"))
    return markup

# Команда /start
@bot.message_handler(commands=['start'])
def start_handler(message):
    chat_id = message.chat.id
    user_data[chat_id] = {
        'name': None,
        'phone': None,
        'inn': None,
        'article': None,
        'date': None,
        'file': [],  # Инициализируем как список
        'file_name': []  # Инициализируем как список
    }
    current_step.pop(chat_id, None)  # Сбрасываем шаги на случай перезапуска
    bot.send_message(
        chat_id,
        (
            "Что умеет бот? Бот поможет собрать информацию о Вас и передать юристу, "
            "который поможет обжаловать штраф по статьям КоАП РФ. Для того чтобы начать, "
            "нажмите на кнопку \"СТАРТ\"."
        ),
        reply_markup=start_button()
    )

# Обработка нажатия на кнопку "СТАРТ"
@bot.callback_query_handler(func=lambda call: call.data == "start_survey")
def start_survey(call):
    chat_id = call.message.chat.id
    current_step[chat_id] = 1  # Начинаем с первого вопроса
    handle_next_step(chat_id)

# Универсальная обработка шагов
def handle_next_step(chat_id):
    step = current_step.get(chat_id, 0)
    print(f"Текущий шаг для {chat_id}: {step}")
    if step == 1:
        bot.send_message(chat_id, "Напишите ваше ФИО:")
    elif step == 2:
        bot.send_message(chat_id, "Укажите ваш номер телефона для связи:")
    elif step == 3:
        bot.send_message(chat_id, "Напишите ИНН вашей организации:", reply_markup=skip_button())
    elif step == 4:
        bot.send_message(chat_id, "Укажите номер статьи КоАП РФ:", reply_markup=skip_button())
    elif step == 5:
        bot.send_message(chat_id, "Дата получения постановления:", reply_markup=skip_button())
    elif step == 6:
        bot.send_message(chat_id, "Предоставьте файл или фотографию постановления:", reply_markup=skip_button())
    elif step == 7:
        finalize_application(chat_id)  # Завершаем обработку данных
    else:
        bot.send_message(chat_id, "Что-то пошло не так. Пожалуйста, начните заново.")

@bot.callback_query_handler(func=lambda call: call.data == "skip")
def skip_step(call):
    chat_id = call.message.chat.id
    current_step[chat_id] += 1
    handle_next_step(chat_id)
    bot.answer_callback_query(call.id)  

# Обработка текста на каждом шаге
@bot.message_handler(func=lambda message: message.chat.id in current_step and message.content_type == 'text')
def process_step(message):
    chat_id = message.chat.id
    step = current_step[chat_id]
    if step == 1:
        user_data[chat_id]['name'] = message.text.strip()
    elif step == 2:
        user_data[chat_id]['phone'] = message.text.strip()
    elif step == 3:
        user_data[chat_id]['inn'] = message.text.strip()
    elif step == 4:
        user_data[chat_id]['article'] = message.text.strip()
    elif step == 5:
        user_data[chat_id]['date'] = message.text.strip()
    current_step[chat_id] += 1
    handle_next_step(chat_id)

# Обработка фотографий и документов
@bot.message_handler(content_types=['photo', 'document'])
def process_file(message):
    chat_id = message.chat.id
    media_group_id = getattr(message, 'media_group_id', None)  # Получаем media_group_id (если есть)

    # Если данных нет, инициализируем их
    if chat_id not in user_data:
        user_data[chat_id] = {
            'file': [],
            'file_name': [],
            'processed_groups': set(),  # Создаём пустой set при инициализации
        }
    else:
        # Если данные уже есть, но processed_groups отсутствует (например, если код обновился), добавляем его
        user_data[chat_id].setdefault('processed_groups', set())

    # Обрабатываем фото
    if message.content_type == 'photo':
        for photo in message.photo:
            file_info = bot.get_file(photo.file_id)
            file_url = f"https://api.telegram.org/file/bot{API_TOKEN}/{file_info.file_path}"
            file_name = f"photo_{file_info.file_id}.jpg"
            user_data[chat_id]['file'].append(file_url)
            user_data[chat_id]['file_name'].append(file_name)

    # Обрабатываем документ
    elif message.content_type == 'document':
        file_info = bot.get_file(message.document.file_id)
        file_url = f"https://api.telegram.org/file/bot{API_TOKEN}/{file_info.file_path}"
        file_name = message.document.file_name
        user_data[chat_id]['file'].append(file_url)
        user_data[chat_id]['file_name'].append(file_name)

    # Проверяем, отправляли ли уже сообщение с кнопкой для этой группы файлов
    if media_group_id:
        if media_group_id in user_data[chat_id]['processed_groups']:
            return  # Если уже обработали эту группу, не дублируем сообщение
        user_data[chat_id]['processed_groups'].add(media_group_id)

    elif 'files_message_sent' in user_data[chat_id]:
        return  # Если уже отправляли сообщение без media_group_id, не дублируем

    # Отправляем сообщение с кнопкой "Подтвердить"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Подтвердить", callback_data="confirm_files"))
    bot.send_message(chat_id, "Файлы успешно получены. Нажмите кнопку 'Подтвердить' или пришлите ещё.", reply_markup=markup)

    # Устанавливаем флаг, что сообщение отправлено
    user_data[chat_id]['files_message_sent'] = True


# Обработка нажатия кнопки "Подтвердить"
@bot.callback_query_handler(func=lambda call: call.data == "confirm_files")
def confirm_files(call):
    chat_id = call.message.chat.id
    current_step[chat_id] += 1  # Переходим к следующему шагу
    handle_next_step(chat_id)
    bot.answer_callback_query(call.id)  # Подтверждаем нажатие кнопки



bot.remove_webhook()
bot.infinity_polling()
