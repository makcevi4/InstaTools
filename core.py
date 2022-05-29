import ast
import time
import json
import string
import random
import schedule
import requests
import configparser
import mysql.connector

from telebot import types
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from telegram_bot_pagination import InlineKeyboardPaginator
from mysql.connector import Error as SQLError
from mysql.connector import InternalError as SQLInternalError
from telebot.apihelper import ApiTelegramException


class Configs:
    users = {'admin': 'администратор', 'user': 'пользователь'}
    subscriptions = {
        'types': {
            'demo': {'title': 'пробная', 'type': 'hour', 'duration': 2},
            'week': {'title': 'недельная', 'type': 'day', 'duration': 7},
            'month': {'title': 'месячная', 'type': 'day', 'duration': 30}
        },
        'statuses': {'active': 'активна', 'inactive': 'неактивна'}
    }
    mailings = {'statuses': {'success': 'успешно', 'waiting': 'ожидание', 'error': 'ошибка'}}

    @staticmethod
    def load():
        processor = configparser.ConfigParser()
        processor.read('data/configs.ini')
        return processor

    def initialization(self):
        configs, processor = dict(), self.load()
        sections = processor.sections()

        for section in sections:
            if section not in configs.keys():
                configs[section] = {}
                for key, value in processor[section].items():
                    try:
                        if key == 'admins':
                            configs[section][key] = [int(value)]
                        else:
                            configs[section][key] = int(value)

                    except ValueError:
                        if ',' not in value:
                            configs[section][key] = value
                        else:
                            data = list()
                            items = value.replace(',', ' ').split()

                            for item in items:
                                try:
                                    data.append(int(item))
                                except ValueError:
                                    data.append(item)

                            configs[section][key] = data

        configs['users'] = self.users
        configs['subscriptions'] = self.subscriptions
        configs['mailings'] = self.mailings

        return configs


class Database:
    tables = ['logs', 'users', 'subscriptions', 'channels', 'subscribers', 'parsings', 'mailings']

    def __init__(self, configs):
        self.configs = configs

    def connect(self):
        configs = {
            'user': self.configs['database']['username'],
            'password': self.configs['database']['password'],
            'host': self.configs['database']['host'],
            'port': self.configs['database']['port'],
            'database': self.configs['database']['name'],
            'raise_on_warnings': True,
        }

        connection = mysql.connector.connect(**configs)
        controller = connection.cursor(dictionary=True)
        return connection, controller

    @staticmethod
    def close(connection, controller):
        connection.close()
        try:
            controller.close()
        except SQLInternalError:
            pass

    def create_pure_table(self, table):
        try:
            query = str()
            connection, controller = self.connect()

            match table:
                case 'logs':
                    query = f"""
                    CREATE TABLE `{table}` (
                    `user` INT(11) NOT NULL,
                    `username` VARCHAR(255) NOT NULL,
                    `usertype` VARCHAR(255) NOT NULL,
                    `date` DATETIME NOT NULL,
                    `action` TEXT NOT NULL
                    )"""

                case 'users':
                    query = f"""
                    CREATE TABLE `{table}` (
                    `id` INT(11) NOT NULL,
                    `name` VARCHAR(255) NOT NULL,
                    `registration` DATETIME NOT NULL,
                    `inviter` INT(11) NOT NULL,
                    `login` VARCHAR(255) NOT NULL,
                    `password` VARCHAR(255) NOT NULL,
                    `secret` VARCHAR(255) NOT NULL,
                    `ban` BOOLEAN NOT NULL,
                    `cause` VARCHAR(255) NOT NULL
                    )"""

                case 'subscriptions':
                    query = f"""
                    CREATE TABLE `{table}` (
                    `type` VARCHAR(255) NOT NULL,
                    `user` INT(11) NOT NULL,
                    `status` VARCHAR(255) NOT NULL,
                    `purchased` DATETIME NOT NULL,
                    `expiration` DATETIME NOT NULL
                    )"""

                case 'channels':
                    query = f"""
                    CREATE TABLE `{table}` (
                    `id` VARCHAR(255) NOT NULL,
                    `title` VARCHAR(255) NOT NULL,
                    `link` VARCHAR(255) NOT NULL,
                    `user` VARCHAR(255) NOT NULL
                    )"""

                case 'subscribers':
                    query = f"""
                    CREATE TABLE `{table}` (
                    `name` VARCHAR(255) NOT NULL,
                    `link` VARCHAR(255) NOT NULL,
                    `channel` VARCHAR(255) NOT NULL,
                    `mailing` BOOLEAN NOT NULL,
                    `text` TEXT NOT NULL
                    )"""

                case 'parsings':
                    query = f"""
                    CREATE TABLE `{table}` (
                    `id` VARCHAR(255) NOT NULL,
                    `date` DATETIME NOT NULL,
                    `user` INT(11) NOT NULL,
                    `channel` VARCHAR(255) NOT NULL,
                    `posts` INT(5) NOT NULL,
                    `subscribers` INT(5) NOT NULL
                    )"""

                case 'mailings':
                    query = f"""
                    CREATE TABLE `{table}` (
                    `id` VARCHAR(255) NOT NULL,
                    `date` DATETIME NOT NULL,
                    `status` VARCHAR(255) NOT NULL,
                    `user` INT(11) NOT NULL,
                    `data` JSON NOT NULL
                    )"""

            controller.execute(query)
            connection.commit()
            self.close(connection, controller)
            return True

        except SQLError as error:
            print(f"ERROR | TYPE: SQL | FUNC: {self.create_pure_table.__name__} | DESC: {error}")
            return False

    def delete_table(self, table):
        status = False
        try:
            connection, controller = self.connect()

            if table in self.tables:
                controller.execute(f"""DROP TABLE `{table}`""")
                connection.commit()
                status = True
            else:
                print(f"ERROR | SQL: Table {table} isn't recognize")

            self.close(connection, controller)
        except SQLError as error:
            print(f"ERROR | TYPE: SQL | FUNC: {self.delete_table.__name__} | DESC: {error}")

        return status

    def recreate_table(self, value='all'):
        if value == 'all':
            for table in self.tables:
                self.delete_table(table)
                self.create_pure_table(table)
        else:
            if value in self.tables:
                self.delete_table(value)
                self.create_pure_table(value)

    def get_data(self, table):
        if table in self.tables:
            connection, controller = self.connect()
            controller.execute(f"""SELECT * FROM `{table}`""")

            return controller.fetchall()

    def get_data_by_value(self, table, value, data, value_=None, data_=None):
        if table in self.tables:
            try:
                connection, controller = self.connect()
                if value_ is None and data_ is None:
                    if type(data) == int:
                        controller.execute(f"""SELECT * FROM `{table}` WHERE `{value}` = {data}""")
                    else:
                        controller.execute(f"""SELECT * FROM `{table}` WHERE `{value}` = '{data}'""")
                else:
                    if type(data) == int:
                        if type(data_) == int:
                            controller.execute(
                                f"""SELECT * FROM `{table}` WHERE `{value}` = {data} OR `{value_}` = {data_}""")
                        else:
                            controller.execute(
                                f"""SELECT * FROM `{table}` WHERE `{value}` = {data} OR `{value_}` = '{data_}'""")
                    else:
                        if type(data_) == int:
                            controller.execute(
                                f"""SELECT * FROM `{table}` WHERE `{value}` = '{data}' OR `{value_}` = {data_}""")
                        else:
                            controller.execute(
                                f"""SELECT * FROM `{table}` WHERE `{value}` = '{data}' OR `{value_}` = '{data_}'""")

                return controller.fetchall()
            except SQLError as error:
                print(f"ERROR | TYPE: SQL | FUNC: {self.get_data_by_value.__name__} | DESC: {error}")
                return False

    def add_data(self, table, **items):
        status, query = False, str()
        if table in self.tables:
            connection, controller = self.connect()
            try:
                match table:
                    case 'logs':
                        query = f"""
                        INSERT INTO `{table}` (`user`, `username`, `usertype`, `date`, `action`)
                        VALUES (
                        {items['user']}, '{items['username']}', '{items['usertype']}',
                        '{datetime.now()}', '{items['action']}'
                        )"""

                    case 'users':
                        query = f"""
                        INSERT INTO `{table}` (
                        `id`, `name`, `registration`, `inviter`, `login`, `password`, `secret`, `ban`, `cause`)
                        VALUES (
                        {items['id']}, '{items['name']}', '{datetime.now()}', 
                        {items['inviter']}, 'None', 'None', 'None', 0, 'None')
                        """

                    case 'subscriptions':
                        status = list(self.configs['subscriptions']['statuses'].keys())[0]
                        query = f"""
                        INSERT INTO `{table}` (`type`, `user`, `status`, `purchased`, `expiration`)
                        VALUES (
                        '{items['type']}', {items['user']}, '{status}', 
                        '{items['dates']['now']}', '{items['dates']['expiration']}')
                        """

                    case 'channels':
                        query = f"""
                        INSERT INTO `{table}` (`id`, `title`, `link`)
                        VALUES ('{items['id']}', '{items['title']}', '{items['link']}')
                        """

                    case 'subscribers':
                        query = f"""
                        INSERT INTO `{table}` (`name`, `link`, `channel`, `mailing`, `text`)
                        VALUES ('{items['name']}', '{items['link']}', '{items['channel']}', 0, '{items['text']}')
                        """

                    case 'parsings':
                        query = f"""
                        INSERT INTO `{table}` (`id`, `date`, `user`, `channel`, `posts`, `subscribers`)
                        VALUES (
                        '{items['id']}', '{datetime.now()}', {items['user']}, '{items['channel']}', 
                        {items['posts']}, {items['subscribers']})
                        """

                    case 'mailings':
                        status = list(self.configs['mailings']['statuses'].keys())[1]
                        query = f"""
                        INSERT INTO `{table}` (`id`, `date`, `status`, `user`, `data`)
                        VALUES ('{items['id']}', '{datetime.now()}', '{status}', {items['user']}, '{items['data']}')
                        """

                if query is not None:
                    status = True
                    controller.execute(query)
                    connection.commit()

            except SQLError as error:
                print(f"ERROR | TYPE: SQL | FUNC: {self.add_data.__name__} | DESC: {error}")
            finally:
                self.close(connection, controller)

        return status

    def change_data(self, table, setter, data, value, column='id'):
        status = False
        if table in self.tables:
            try:
                connection, controller = self.connect()
                if type(data) == int or type(data) == float:
                    if type(value) == int:
                        controller.execute(
                            f"""UPDATE `{table}` SET `{setter}` = {data} WHERE `{table}`.`{column}` = {value}""")
                    else:
                        controller.execute(
                            f"""UPDATE `{table}` SET `{setter}` = {data} WHERE `{table}`.`{column}` = '{value}'""")
                elif type(data) == str:
                    if type(value) == int or type(value) == float:
                        controller.execute(
                            f"""UPDATE `{table}` SET `{setter}` = '{data}' WHERE `{table}`.`{column}` = {value}""")
                    else:
                        controller.execute(
                            f"""UPDATE `{table}` SET `{setter}` = '{data}' WHERE `{table}`.`{column}` = '{value}'""")
                elif type(data) == list:
                    controller.execute(
                        f'''UPDATE `{table}` SET `{setter}` = "{data}" WHERE `{table}`.`{column}` = {value}''')

                connection.commit()
                connection.close()
                self.close(connection, controller)
                status = True
            except SQLError as error:
                print(f"ERROR | TYPE: SQL | FUNC: {self.change_data.__name__} | DESC: {error}")
        return status

    def delete_data(self, table, value, data):
        status = False
        if table in self.tables:
            connection, controller = self.connect()
            try:
                if type(data) == int:
                    controller.execute(f"""DELETE FROM `{table}` WHERE {value} = {data}""")
                else:
                    controller.execute(f"""DELETE FROM `{table}` WHERE {value} = '{data}'""")

                connection.commit()
                connection.close()
                status = True
            except SQLError as error:
                print(f"ERROR | TYPE: SQL | FUNC: {self.delete_data.__name__} | DESC: {error}")
            finally:
                self.close(connection, controller)
        return status


class Sessions:
    def __init__(self):
        self.admins = dict()
        self.users = dict()

    def start(self, identifier, usertype, session, message=None, userid=None):
        template = {
            'type': session,
            'message': {'id': message},
            'actions': {'step': 0, 'data': {}}
        }

        match usertype:
            case 'admin':
                self.admins[identifier] = template
                self.admins[identifier]['user'] = {'id': userid}

            case 'user':
                self.users[identifier] = template

    def clear(self, usertype, identifier):
        try:
            match usertype:
                case 'admin':
                    del self.admins[identifier]
                case 'user':
                    del self.users[identifier]
        except KeyError:
            try:
                del self.admins[identifier]
            except KeyError:
                pass

            try:
                del self.users[identifier]
            except KeyError:
                pass

    def reset(self, usertype, identifier, session_type=None, message=None, userid=None):
        match usertype:
            case 'admin':
                if usertype is None:
                    session_type = self.admins[identifier]['type']

                if message is None:
                    try:
                        message = self.admins[identifier]['message']['id']
                    except KeyError:
                        message = None

                if userid is None:
                    try:
                        message = self.admins[identifier]['user']['id']
                    except KeyError:
                        message = None
            case 'user':
                if usertype is None:
                    session_type = self.users[identifier]['type']

                if message is None:
                    try:
                        message = self.users[identifier]['message']['id']
                    except KeyError:
                        message = None

        self.clear(usertype, identifier)
        self.start(identifier, usertype, session_type, message)


class Processes:
    def __init__(self, bot, texts, buttons):
        self.bot = bot
        self.texts = texts
        self.buttons = buttons

    def mailing(self):
        pass

    def run(self):
        schedule.every(1).seconds.do(
            self.mailing
        )

        while True:
            schedule.run_pending()
            time.sleep(1)


class Handler:
    def __init__(self, configs, database):
        self.configs = configs
        self.database = database

    @staticmethod
    def paginator(character_pages, option, page=1, close=True, **data):
        pattern = f"set-page-{option}-" + "{page}"

        try:
            if len(option.replace('-', ' ').split()) > 1 and 'user' in option:
                pattern = f"set-page-{option}-{data['id']}-" + "{page}"
        except KeyError:
            pass

        paginator = InlineKeyboardPaginator(
            len(character_pages),
            current_page=page,
            data_pattern=pattern
        )

        try:
            if close:
                markups = ast.literal_eval(paginator.markup)
                markups['inline_keyboard'].append([{"text": "❌", "callback_data": "close-page"}])
                markups = str(markups).replace('\'', '"')
            else:
                markups = paginator.markup
        except ValueError:
            if close:
                markups = types.InlineKeyboardMarkup()
                markups.add(types.InlineKeyboardButton('❌', callback_data=f"close-page"))
            else:
                markups = paginator.markup

        return character_pages[page - 1], markups

    @staticmethod
    def file(action, file, data=None):
        buffering = action[0] if action == 'read' or action == 'write' else 'r'

        with open(f'data/{file}.json', buffering, encoding='utf-8') as file:
            match action:
                case 'read':
                    return json.load(file)
                case 'write':
                    json.dump(data, file, ensure_ascii=False)

    def initialization(self, mode, **data):
        match mode:
            case 'user':
                users, log, additional = self.format('list', 'users', 'ids'), str(), None
                username = self.format('str', 'user', 'username', first=data['first'], last=data['last'])

                if data['user'] not in users:
                    inviter = 0

                    try:
                        if len(data['commands']) == 2:
                            inviter_data = self.database.get_data_by_value('users', 'id', data['commands'][1])
                            additional = f"Пользователь использовал реферальный код `{data['commands'][1]}`, "
                            if len(inviter_data) and not inviter_data[0]['ban']:
                                inviter = inviter_data[0]['id']
                                additional += f"пригласитель [{inviter_data[0]['name']}]" \
                                              f"(tg://user?id={inviter_data[0]['id']}) | " \
                                              f"ID: {inviter_data[0]['id']}."
                            else:
                                additional += "но пригласитель либо не найден, либо заблокирован."
                    except KeyError:
                        pass

                    log = f"Добавлен новый пользователь [{username}](tg://user?id={data['user']}). " \
                          f"{'' if additional is None else additional}"
                    self.database.add_data('users', id=data['user'], name=username, inviter=inviter)
                else:
                    log = "Пользователь использовал команду `/start` для запуска/перезапуска бота."

                if 'commands' in data.keys():
                    usertype = self.recognition('usertype', user=data['user'])
                    self.database.add_data('logs', user=data['user'], username=username, usertype=usertype, action=log)

    def format(self, mode, option=None, value=None, **data):
        result = None

        match mode:
            case 'list':
                result = list()

                match option:
                    case 'users':
                        users = self.database.get_data('users')

                        if value == 'ids':
                            for user in users:
                                result.append(user['id'])

            case 'dict':
                result = dict()

            case 'str':
                result = str()

                match option:
                    case 'user':
                        if value == 'username':
                            name, surname = data['first'], data['last']

                            if name == 'ᅠ' or name is None or name == '':
                                name = 'Неизвестно'
                            else:
                                name = name

                            if surname is None or surname == '':
                                surname = ''
                            else:
                                surname = surname

                            result = f"{name}{f' {surname}' if surname != '' else surname}"

                        elif value == 'instagram-password':
                            password = data['password']
                            result = f'{password[0]}{"•" * (len(password) - 2)}{password[-1]}'
            case 'int':
                result = 0

        return result

    def recognition(self, mode, option=None, **data):
        result = None

        match mode:
            case 'ban':
                if option == 'user':
                    userdata = self.database.get_data_by_value('users', 'id', data['user'])[0]
                    result = True if userdata['ban'] else False

            case 'usertype':
                result = 'admin' if data['user'] in self.configs['main']['admins'] else 'user'

            case 'subscription':
                if option == 'price':
                    settings = self.file('read', 'settings')
                    prices, currency = settings['prices'], settings['main']['currency']
                    result = "Бесплатно" if prices[data['type']] == 0 else f"{prices[data['type']]} {currency}"

                elif option == 'user':
                    template = '%H:%M:%S / %d.%m.%Y'
                    subscriptions = self.database.get_data_by_value('subscriptions', 'user', data['user'])

                    if len(subscriptions):
                        for subscription in subscriptions:
                            if subscription['status'] == 'active':
                                result = {
                                    'title': self.configs['subscriptions']['types'][subscription['type']]['title'],
                                    'expiration': subscription['expiration'].strftime(template)
                                }

            case 'emoji':
                if option == 'status':
                    match data['status']:
                        case 'accepted' | 'success' | 'active':
                            result = '🟢'
                        case 'processing' | 'waiting':
                            result = '🟡'
                        case 'rejected' | 'error' | 'inactive':
                            result = '🔴'
        return result

    def generate(self, mode):
        result = None
        match mode:
            case 'unique-id':
                chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
                result = ''.join(random.choice(chars) for x in range(random.randint(10, 12)))

            case 'secret-key':
                result = Fernet.generate_key()

        return result


class Driver:
    def __init__(self):
        pass


class Cryptor:
    def __init__(self, handler):
        self.handler = handler

    def encrypt(self, data, secret=None):
        secret = self.handler.generate('secret-key') if secret is None else secret.encode('utf-8')
        processor = Fernet(secret)
        return {
            'secret': secret.decode('utf-8'),
            'data': processor.encrypt(data.encode('utf-8')).decode('utf-8')}

    @staticmethod
    def decrypt(secret, data):
        processor = Fernet(secret.encode('utf-8'))
        return processor.decrypt(data.encode('utf-8')).decode('utf-8')


class Texts:
    def __init__(self, configs, database, handler):
        self.configs = configs
        self.database = database
        self.handler = handler

    def error(self, mode, option=None, **data):
        text = "🚫 *Ошибка*\n\n⚠️ "

        match mode:
            case 'embedded':
                match option:
                    case 'short-password':
                        text = 'Пароль слишком короткий. Длинна должна быть не менее 6 символов.'

        return text

    def warning(self, mode, option=None, **data):
        text = "🚫 *Ошибка*\n\n⚠️ "

        match mode:
            case 'unset-data':
                text = "⚠️ *Внимание* ⚠️\n\n" \
                       "🔔 У тебя не установлены логин и пароль от инстаграм аккаунта. Нужно указать данные, " \
                       "для продолжения действия.\n\n" \
                       "🔔  Ты можешь ввести данные для входа в разделе «⚙️ Настройки» или " \
                       "же нажав кнопку «🖋 Ввести данные»\n\n" \
                       "⚠️ Все конфиденциальные данные пользователей хранятся в зашифрованном виде и " \
                       "ни администрация, ни технический отдел не имеет доступа к ним."

        return text

    def success(self, mode, option=None, **data):
        text = "✅ *Успешно*\n\n🔔 "

        match mode:
            case 'established-instagram-data':
                option = 'изменены' if option == 'change' else 'установлены'
                text += f"Данные для авторизации успешно {option} и надёжно зашифрованы. " \
                        f"Теперь ты можешь использовать функции «📊 Анализ» и «📨 Рассылка»."

        return text
    def menu(self, usertype, mode, **data):
        text = str()

        match usertype:
            case 'admin':
                match mode:
                    case 'main':
                        text = "*АДМИН-ПАНЕЛЬ*\n\n" \
                               f"✏️ Логов: *{len(self.database.get_data('logs'))}*\n" \
                               f"👥 Пользователей: *{len(self.database.get_data('users'))}*\n" \
                               f"📨 Рассылок: *{len(self.database.get_data('mailings'))}*\n" \
                               f"⭐️ Подписок: *{len(self.database.get_data('subscriptions'))}*\n\n"

                    case 'users':
                        text += "*Пользователи*\n\n" \
                                "📍 Доступные действия:\n" \
                                "1️⃣ Просмотр всех пользователей\n" \
                                "2️⃣ Просмотр и изменение данных пользователя\n\n" \
                                "🔽 Выбери действие 🔽"

            case 'user':
                userdata = self.database.get_data_by_value('users', 'id', data['user'])[0]

                match mode:
                    case 'main':
                        subscription = self.handler.recognition('subscription', 'user', user=userdata['id'])

                        text = "*ГЛАВНОЕ МЕНЮ*\n\n" \
                               f"⭐️ Текущая подписка: " \
                               f"*{'Нет' if subscription is None else subscription['title']}*\n"

                        if subscription is not None:
                            text += f"🗓 Подписка истекает: *{subscription['expiration']}*\n"

                        text += f"📊 Проведено анализа: *" \
                                f"{len(self.database.get_data_by_value('parsings', 'user', userdata['id']))}* раз\n" \
                                f"📨 Проведено рассылок: " \
                                f"*{len(self.database.get_data_by_value('mailings', 'user', userdata['id']))}* " \
                                f"шт.\n\n" \
                                f"*Подписки*\n"

                        for subscription, data in self.configs['subscriptions']['types'].items():
                            text += f" - {data['title'].capitalize()}: " \
                                    f"*{self.handler.recognition('subscription', 'price', type=subscription)}*\n"

                        text += "\n🔽 Выбери действие 🔽"

                    case 'parsing':
                        parsings = len(self.database.get_data_by_value('parsings', 'user', userdata['id']))
                        text += "*Анализ данных*\n\n" \
                                f"🧮 Всего проанализировано: *{parsings}* раз\n" \
                                "🛍 Страниц проанализировано: *{}*\n" \
                                "📰 Постов проанализировано: *{}*\n" \
                                "👥 Пользователей найдено: *{}*\n\n" \
                                "📌 Доступные действия:\n\n" \
                                "1️⃣ Начать новый анализ страниц\n"

                        if parsings > 0:
                            text += "2️⃣ Посмотреть проведённые анализы страниц\n" \
                                    "3️⃣ Посмотреть проанализированные каналы\n"

                        text += "\n🔽 Выбери действие 🔽"

                    case 'mailing':
                        subscribers = len([])  # --- #
                        mailings = len(self.database.get_data_by_value('mailings', 'user', data['user']))

                        text += "*Рассылка*\n\n" \
                                f"📨 Проведено рассылок: *{mailings}*\n" \
                                f"👥 Доступно пользователей к рассылке: *{subscribers}*\n"

                        if subscribers > 0 or mailings > 0:
                            text += "\n📌  Доступные действия:\n"

                            if subscribers > 0:
                                text += "🔹 Рассылка сообщения пользователям\n"
                            if mailings > 0:
                                text += "🔸 Просмотр проведённых рассылок\n"

                        if subscribers == 0:
                            text += "\n⚠️ *Рассылка сейчас недоступна*, так как в базе ещё нет пользователей " \
                                    "для рассылки.\n" \
                                    "🔔Сперва тебе нужно провести анализ страниц, в разделе *«📊 Анализ»* и после " \
                                    "того, как база пользователей будет наполнена рассылка станет доступной.\n"

                        text += f"\n🔽 {'Выбери действие' if subscribers > 0 or mailings > 0 else 'Вернуться назад'} 🔽"
        return text

    # def control(self, usertype, mode):
    #     text = str()
    #
    #     match usertype:
    #         case 'admin':
    #             pass
    #
    #         case 'user':
    #
    #             match mode:
    #                 case ''
    #
    #     return text

    def processes(self, user, mode, option=None, step=1, **data):
        text = str()

        match user:
            case 'admin':
                if mode == 'find-user':
                    pass

            case 'user':
                if mode == 'set-instagram-data':
                    final, setter = False, None
                    text = f"*Ввод данных Instagram ({step}/3)*\n\n"

                    match step:
                        case 1:
                            setter = 'логин'
                        case 2:
                            setter = 'пароль'
                        case 3:
                            final = True

                    if 'error' in data.keys():
                        text += f"⚠️ *{data['error']}*\n\n"

                    login = data['login'] if 'login' in data.keys() else 'Не указан'
                    password = self.handler.format('str', 'user', 'instagram-password', password=data['password']) \
                        if 'password' in data.keys() else 'Не указан'
                    additional = f'Нужно указать: *{setter}* от аккаунта' \
                        if not final else 'Подтверди введённые логин и пароль для завершения установки данных.'
                    text += f"👤 Логин: *{login}*\n" \
                            f"🔐 Пароль: *{password}*\n\n" \
                            f"📌 {additional}\n\n" \
                            f"🔽 {'Введи данные' if not final else 'Подтверди данные'} 🔽"

                elif mode == 'parse-pages':
                    final = None
                    text = f"*Анализ страниц ({step}/3)*\n\n"

                    match step:
                        case 1:
                            text += "📌 Для того, чтоб начать анализировать Instagram-страницы введи через " \
                                    "запятую ссылки на страницы, которые хочешь проанализировать " \
                                    "(Если нужно проанализировать только одну страницу, тогда просто отправь " \
                                    "ссылку на неё).\n\n" \
                                    "*Примеры ссылок*\n" \
                                    "Одна: `instagram.com/skemmeks`\n" \
                                    "Несколько: `instagram.com/skemmeks, instagram.com/bgnsk_m`\n\n" \
                                    "⚠️ Время анализа страниц зависит от их количества, чем больше страниц, " \
                                    "тем дольше будет идти процесс анализа. Просьба иметь терпение и ожидать " \
                                    "полного окончания анализа.\n\n"

                    text += f"🔽 {'Введи данные' if not final else 'Подтверди данные'} 🔽"
        return text


class Buttons:
    def __init__(self, configs, database, handler):
        self.configs = configs
        self.database = database
        self.handler = handler

    @staticmethod
    def cancel_reply(text):
        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        return markup.add(types.KeyboardButton(f'❌ Отменить {text}'))

    @staticmethod
    def cancel_inline(action, user=None, additional=None):
        markup = types.InlineKeyboardMarkup()
        query = f'cancel-{action}-{user}' if user else f'cancel-{action}'
        return markup.add(types.InlineKeyboardButton(
            '🚫 Отменить', callback_data=f"{f'{query}-{additional}' if additional is not None else query}"))

    @staticmethod
    def comeback_reply(text):
        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        return markup.add(types.KeyboardButton(f'↩️ Назад к {text}'))

    @staticmethod
    def comeback_inline(action, text=None, **data):
        markup = types.InlineKeyboardMarkup()
        try:
            query = f"comeback-{action}-{data['id']}"
        except KeyError:
            query = f"comeback-{action}"

        return markup.add(types.InlineKeyboardButton(
            '↩️ Назад' if text is None else f'↩️ Назад к {text}', callback_data=query))

    @staticmethod
    def set_data(route, action='set', text='ввести'):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(f'🖋 {text.capitalize()} данные',
                                              callback_data=f'{action}-instagram-data-{route}'))
        return markup

    @staticmethod
    def confirm(action, **data):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('✅ Подтвердить', callback_data=f"confirm-{action}"))

        if 'comeback' in data.keys():
            markup.add(types.InlineKeyboardButton('↩️ Назад', callback_data=f"comeback-{data['comeback']}"))

        if 'cancel' in data.keys():
            markup.add(types.InlineKeyboardButton('🚫 Отменить', callback_data=f"cancel-{data['cancel']}"))

        return markup

    def menu(self, usertype, menu, additional=False, markups_type='reply', width=2, **data):
        markup, comeback, query = None, True, None

        if markups_type == 'reply':
            markup = types.ReplyKeyboardMarkup(row_width=width, resize_keyboard=True)
        elif markups_type == 'inline':
            markup = types.InlineKeyboardMarkup()

        match usertype:
            case 'admin':
                match menu:
                    case 'main':
                        comeback = 'функционалу'
                        markup.add(
                            types.KeyboardButton('👨🏻‍💻 Пользователи'),
                            types.KeyboardButton('📊 Анализ'),
                            types.KeyboardButton('📨 Рассылки'),
                            types.KeyboardButton('⭐️ Проект')
                        )

                    case 'users':
                        markup.add(
                            types.KeyboardButton('👁 Посмотреть всех'),
                            types.KeyboardButton('🕹 Управлять')
                        )

                    case 'user':
                        comeback = False
                        user = data['id']
                        markup, markups, row, additional = dict(), list(), list(), dict()

                        items = {
                            '⛔️ Блокировка': {'type': 'control', 'action': 'ban'},
                            '💰 Баланс': {'type': 'control', 'action': 'balance'},
                        }

                        if len(self.database.get_data_by_value('logs', 'user', user)):
                            items['⚙️ Действия'] = {'type': 'get', 'action': 'logs'}

                        if len(self.database.get_data_by_value('payments', 'user', user)):
                            items['💳 Платежи'] = {'type': 'get', 'action': 'payments'}

                        if len(self.database.get_data_by_value('subscriptions', 'user', user)):
                            items['⭐️ Подписки'] = {'type': 'get', 'action': 'subscriptions'}

                        if len(self.database.get_data_by_value('users', 'inviter', user)):
                            items['🔗 Рефералы'] = {'type': 'get', 'action': 'referrals'}

                        if len(self.database.get_data_by_value('mailings', 'user', user)):
                            items['📨 Рассылки'] = {'type': 'get', 'action': 'mailings'}

                        for name, values in items.items():
                            if len(row) < width:
                                row.append({
                                    'text': name,
                                    'callback_data': f'{values["type"]}-user-{user}-{values["action"]}'
                                })
                                if values["action"] == 'ban':
                                    markups.append(row)
                                    row = list()

                            if len(row) == width:
                                markups.append(row)
                                row = list()
                        else:
                            if len(row) != 0:
                                markups.append(row)

                        markup['inline_keyboard'] = markups
                        markup = str(markup).replace('\'', '"')

                    case 'services':
                        markup.add(
                            types.KeyboardButton('➕ Добавить'),
                            types.KeyboardButton('⚙️ Управлять') if len(self.database.get_data('services')) > 0 else ''
                        )

            case 'user':
                match menu:
                    case 'main':
                        comeback = False
                        markup.add(
                            types.KeyboardButton('📊 Анализ'),
                            types.KeyboardButton('📨 Рассылка'),
                            types.KeyboardButton('🗞 Информация')
                        )

                    case 'parsing':
                        parsings = len(self.database.get_data_by_value('parsings', 'user', data['user']))
                        markup.add(types.KeyboardButton('➕ Начать анализ'))

                        if parsings > 0:
                            markup.add(
                                types.KeyboardButton('📊  Анализы'),
                                types.KeyboardButton('🛍 Страницы')
                            )

                    case 'mailing':
                        subscribers = len([])  # --- #
                        mailings = len(self.database.get_data_by_value('mailings', 'user', data['user']))

                        if subscribers > 0:
                            markup.add(types.KeyboardButton('➕ Начать рассылку'))
                        if mailings > 0:
                            markup.add(types.KeyboardButton('👁 Посмотреть рассылки'))

        if comeback:
            if markups_type == 'reply':
                if usertype == 'user':
                    markup.add(types.KeyboardButton('↩️ Назад к меню'))
                elif usertype == 'admin':
                    markup.add(types.KeyboardButton(f'↩️ Назад к {"админ панели" if comeback is True else comeback}'))

                else:
                    markup.add(types.KeyboardButton(f'↩️ Назад к '
                                                    f'{"главной панели" if comeback is True else comeback}'))
            else:
                markup.add(types.InlineKeyboardButton("↩️ Назад", callback_data=f"comeback-to-{query}"))

        return markup

if __name__ == '__main__':
    _configs = Configs().initialization()
    _database = Database(_configs)
    _database.recreate_table()
