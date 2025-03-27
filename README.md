# Краткая инструкция по развёртки бота на Linux Debian

## Создание каталога и файла
Создаём каталог для бота:
```sh
mkdir BotBitrix
```
Переходим в созданный каталог:
```sh
cd BotBitrix
```
Создаём файл бота `main.py`:
```sh
nano main.py
```
Вставляем туда содержание кода из репозитория.

## Подготовка кода
### Вебхук
#### Создание вебхука
В Битрикс24 переходим в Настройки --> Интеграции --> RestAPI --> Другое --> Входящий вебхук .
Копируем строку из поля Вебхук для вызова rest api и в поле\
Настройка прав выдаём необходимые права на создание сделки и доступа к диску.

### Редактирование кода
#### Вебхук и токен
Копируем вебхук из Битрикс24 и вставляем его в переменную `BITRIX_WEBHOOK`, а в переменнуж 'API_TOKEN` помещаем Telegram-токен.
Нас интересуют строки 6 и 8.
```python

API_TOKEN = 'СЮДА_ТОКЕН_БОТА'

BITRIX_WEBHOOK = 'СЮДА_ВЕБХУК_БИТРИКСА'
```
Telegram-токен возможно заменить при помощи @BotFather
#### Пользовательские поля
Теперь намнужно создать пользовательские поля в которые будут помещаться данные из Telegram.\
Идём в Настройки --> Настройки форм и отчетов --> Пользовательские поля . Далее нажимаем на кнопку "Список полей" у раздела "Сделка".\
Теперь при помощи кнопки "Добавить поле" будем создавать поля. \
В URL-адресе каждого поля имеется ID этого поля.\
Пример:
```http
https://b24-
test.bitrix24.ru/crm/configs/fields/CRM_DEAL/edit/UF_CRM_1234567890
```
Из этого URL нам нужно выцепить ID поля. Оно находится после `/edit/` . То есть, ID нашего поля ИНН - UF_CRM_1234567890

Ищем в коде main.py следующую функцию и вставляем :
```python
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
```
#### Папка для скачивания файлов
Нашему боту требуется куда-то сохранять скачанные файлы.\
Нам нужно в разделе "Диск" Битрикс24 создать папку с произвольным названием. Например "Файлы из Telegram".\
Затем нам нужно нажать на эту папку, выбрать "Поделится", после "Скопировать внутреннюю ссылку". Получим вот такой результат:
```http
https://b24-test.bitrix24.ru/bitrix/tools/disk/focus.php?
folderId=93&action=openFolderList&ncc=1
```
Из этой ссылки нам нужно выцепить ID папки. Оно находится после `folderId=` . То есть, в нашем случае, ID папки будет 93 .\
Теперь, зная ID папки нужно указать его в функции `upload_file_to_bitrix` в значении `folder_id=`
```python
def upload_file_to_bitrix(file_url, file_name, folder_id=93): # Это id папки на Битрикс24
```
И аналогично в функции `finalize_application` в значении `folder_id=`
```python
def finalize_application(chat_id):
    data = user_data.get(chat_id, {})
    file_links = []
    # Проверяем, есть ли файлы
    if data.get('file') and data.get('file_name'):
        for file_url, file_name in zip(data['file'], data['file_name']):
            bitrix_link = upload_file_to_bitrix(file_url, file_name, folder_id=93) # Указываем то же id папки Битрикс24 что было ранее
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
```
На это манипуляции с кодом закончены.
### Установка пакетов
Устанавливаем пакет для создания виртуального окружения:
```sh
apt install -y python3.11-venv
```
Создаём виртуальное окружение:
```sh
python3 -m venv venv
```
Включаем виртуальное окружение:
```sh
source venv/bin/activate
```
Устанавливаем основную библиотеку:
```sh
pip install pyTelegramBotAPI
```
Выходим из виртуального окружения:
```sh
deactivate
```

### Создание службы
Для автозапуска бота в случае перезапуска сервера нужно будет создать службу для бота.\
Создаём службу:
```sh
nano /etc/systemd/system/botbitrix.service
```
Пишем в файле конфигурации службы:
```
[Unit]
Description=Telegram Bot for Bitrix
After=network.target
[Service]
User=root
WorkingDirectory=/root/BotBitrix
ExecStart=/root/BotBitrix/venv/bin/python3
/root/BotBitrix/main.py
Restart=always
[Install]
WantedBy=multi-user.target
```
Заставляем systemd перечитать все конфигурационные файлы:
```sh
systemctl daemon-reload
```
Включаем бота в автозапуск:
```sh
systemctl enable botbitrix
```
Запускаем бота:
```sh
systemctl start botbitrix
```
Проверяем статус службы бота:
```sh
systemctl status botbitrix
```
На этом развёртывание и запуск бота закончен.
