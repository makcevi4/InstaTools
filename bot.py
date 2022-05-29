import time
import json
import logging

from datetime import datetime
from telebot.apihelper import ApiTelegramException


def run(bot, configs, sessions, database, driver, cryptor, handler, texts, buttons):
    @bot.message_handler(commands=['start', 'admin'])
    def start(message):
        commands = message.text.replace('/', '').split()
        handler.initialization('user', commands=commands,
                               user=message.from_user.id,
                               first=message.from_user.first_name,
                               last=message.from_user.last_name)

        if not handler.recognition('ban', 'user', user=message.from_user.id):
            match commands[0]:
                case 'start':
                    bot.send_message(message.chat.id, texts.menu('user', 'main', user=message.from_user.id),
                                     parse_mode='markdown', reply_markup=buttons.menu('user', 'main'))

                case 'admin':
                    usertype = handler.recognition('usertype', user=message.from_user.id)

                    if usertype == 'admin':
                        bot.send_message(message.chat.id, texts.menu('admin', 'main'), parse_mode='markdown',
                                         reply_markup=buttons.menu('admin', 'main'))
                    else:
                        username = database.get_data_by_value('users', 'id', message.from_user.id)[0]['name']
                        database.change_data('users', 'ban', 1, message.from_user.id)
                        database.change_data('users', 'cause', 'abuse', message.from_user.id)
                        database.add_data('logs', user=message.from_user.id, username=username, usertype=usertype,
                                          action="Пользователь попытался запустить админ-панель, но не смог, так как "
                                                 "у него нет прав. Пользователь был автоматически заблокирован.")

                        bot.send_message(message.chat.id, texts.error('banned', user=message.from_user.id),
                                         parse_mode='markdown', reply_markup=buttons.support())

        else:
            bot.send_message(message.chat.id, texts.error('banned', user=message.from_user.id), parse_mode='markdown',
                             reply_markup=buttons.support())

    @bot.message_handler(content_types=['text'])
    def text_handler(message):
        handler.initialization('user', user=message.from_user.id,
                               first=message.from_user.first_name,
                               last=message.from_user.last_name)

        if handler.recognition('ban', 'user', user=message.from_user.id):
            bot.send_message(message.chat.id, texts.error('banned', user=message.from_user.id), parse_mode='markdown',
                             reply_markup=buttons.support())
        else:
            usertype = handler.recognition('usertype', user=message.from_user.id)

            # Buttons handling | Comeback
            if '↩️ Назад к' in message.text:
                sessions.clear(usertype, message.from_user.id)

                if usertype == 'admin':
                    if 'функционалу' in message.text:
                        bot.send_message(message.from_user.id, texts.menu('user', 'main', user=message.from_user.id),
                                         parse_mode='markdown', reply_markup=buttons.menu('user', 'main'))

                    elif 'админ панели' in message.text:
                        bot.send_message(message.from_user.id, texts.menu('admin', 'main'),
                                         parse_mode='markdown', reply_markup=buttons.menu('admin', 'main'))

                    elif 'пользователям' in message.text:
                        bot.send_message(message.from_user.id, texts.menu('admin', 'users'),
                                         parse_mode='markdown', reply_markup=buttons.menu('admin', 'users'))

                if 'меню' in message.text:
                    bot.send_message(message.chat.id, texts.menu('user', 'main', user=message.from_user.id),
                                     parse_mode='markdown', reply_markup=buttons.menu('user', 'main'))

            # Buttons handling | Cancel
            if '❌ Отменить' in message.text:
                sessions.clear(usertype, message.from_user.id)

                if usertype == 'admin':
                    if 'поиск' in message.text:
                        if 'пользователя' in message.text:
                            bot.send_message(message.from_user.id, texts.menu('admin', 'users'),
                                             parse_mode='markdown', reply_markup=buttons.menu('admin', 'users'))

                if 'ввод данных' in message.text:
                    bot.send_message(
                        message.from_user.id, texts.menu('user', 'parsing', user=message.from_user.id),
                        parse_mode='markdown', reply_markup=buttons.menu('user', 'parsing', user=message.from_user.id))
                if 'анализ страниц':
                    bot.send_message(
                        message.from_user.id, texts.menu('user', 'parsing', user=message.from_user.id),
                        parse_mode='markdown', reply_markup=buttons.menu('user', 'parsing', user=message.from_user.id))


            #
            if '📊 Анализ' in message.text:
                bot.send_message(
                    message.from_user.id, texts.menu('user', 'parsing', user=message.from_user.id),
                    parse_mode='markdown', reply_markup=buttons.menu('user', 'parsing', user=message.from_user.id))

            if '➕ Начать анализ' in message.text:
                userdata = database.get_data_by_value('users', 'id', message.from_user.id)[0]

                if userdata['login'] == 'None' and userdata['password'] == 'None':
                    text = texts.warning('unset-data')
                    markups = buttons.set_data('parsing')
                else:
                    sessions.start(message.from_user.id, 'user', 'parse-pages', message.id)
                    sessions.users[message.from_user.id]['actions']['step'] += 1
                    text = texts.processes('user', 'parse-pages', step=1)
                    markups = buttons.cancel_reply('анализ страниц')

                delete = bot.send_message(message.from_user.id, text, parse_mode='markdown', reply_markup=markups)

                if message.from_user.id in sessions.users.keys():
                    sessions.users[message.from_user.id]['message']['delete'] = delete.id

            # Handling | Set data | Instagram login and password
            if message.from_user.id in sessions.users \
                    and sessions.users[message.from_user.id]['type'] == 'parse-pages':
                if sessions.users[message.from_user.id]['message']['id'] != message.message_id:
                    data = sessions.users[message.from_user.id]['actions']['data']

                    if 'login' not in data.keys() and 'password' not in data.keys():
                        secret = handler.file('read', 'keys')[str(message.from_user.id)]
                        userdata = database.get_data_by_value('users', 'id', message.from_user.id)[0]

                        secret = cryptor.decrypt(secret, userdata['secret'])
                        login = cryptor.decrypt(secret, userdata['login'])
                        password = cryptor.decrypt(secret, userdata['password'])
                        sessions.users[message.from_user.id]['actions']['data']['login'] = login
                        sessions.users[message.from_user.id]['actions']['data']['password'] = password
                        data = sessions.users[message.from_user.id]['actions']['data']

                    print(data)




            #
            if '📨 Рассылка' in message.text:
                bot.send_message(
                    message.from_user.id, texts.menu('user', 'mailing', user=message.from_user.id),
                    parse_mode='markdown', reply_markup=buttons.menu('user', 'mailing', user=message.from_user.id))

            # ------------ #
            # Handling | Set data | Instagram login and password
            if message.from_user.id in sessions.users \
                    and sessions.users[message.from_user.id]['type'] == 'set-data':
                if sessions.users[message.from_user.id]['message']['id'] != message.message_id:
                    mode = sessions.users[message.from_user.id]['actions']['data']['type']
                    step = sessions.users[message.from_user.id]['actions']['step']
                    delete = sessions.users[message.from_user.id]['message']['delete']
                    text, markups = str(), str()
                    bot.delete_message(message.chat.id, message.id)

                    match mode:
                        case 'instagram':
                            match step:
                                case 1:
                                    step += 1
                                    sessions.users[message.from_user.id]['actions']['data']['login'] = message.text
                                    sessions.users[message.from_user.id]['actions']['step'] = step

                                    text = texts.processes('user', 'set-instagram-data', step=step, login=message.text)
                                    markups = buttons.comeback_inline('to-set-instagram-login')
                                case 2:
                                    login = sessions.users[message.from_user.id]['actions']['data']['login']

                                    if len(message.text) < 6:
                                        text = texts.processes('user', 'set-instagram-data', step=step, login=login,
                                                               error=texts.error('embedded', 'short-password'))
                                        markups = buttons.comeback_inline('to-set-instagram-login')

                                    else:
                                        step += 1
                                        sessions.users[message.from_user.id]['actions']['data']['password'] = \
                                            message.text
                                        sessions.users[message.from_user.id]['actions']['step'] = step
                                        text = texts.processes('user', 'set-instagram-data', step=step,
                                                               login=login, password=message.text)
                                        markups = buttons.confirm('established-data-instagram',
                                                                  comeback='to-set-instagram-password')

                    bot.delete_message(message.chat.id, delete)
                    delete = bot.send_message(message.chat.id, text, parse_mode='markdown', reply_markup=markups)
                    sessions.users[message.from_user.id]['message']['delete'] = delete.id

    @bot.callback_query_handler(func=lambda call: True)
    def queries_handler(call):
        queries = call.data.replace('-', ' ').split()
        print(queries)

        match queries[0]:
            case 'comeback':
                text, markups = str(), str()

                if 'to-set-instagram' in call.data:
                    if call.from_user.id in sessions.users:
                        step = sessions.users[call.from_user.id]['actions']['step']
                        step -= 1
                        match queries[-1]:
                            case 'login':
                                text = texts.processes('user', 'set-instagram-data', step=step)
                                markups = buttons.cancel_reply('ввод данных')
                            case 'password':
                                pass
                                login = sessions.users[call.from_user.id]['actions']['data']['login']
                                text = texts.processes('user', 'set-instagram-data', step=step, login=login)
                                markups = buttons.comeback_inline('to-set-instagram-login')

                        sessions.users[call.from_user.id]['actions']['step'] = step

                    else:
                        bot.answer_callback_query(callback_query_id=call.id, text='❎ Действие устарело')
                        bot.send_message(
                            call.from_user.id, texts.menu('user', 'parsing', user=call.from_user.id),
                            parse_mode='markdown', reply_markup=buttons.menu('user', 'parsing', user=call.from_user.id))
                try:
                    bot.edit_message_text(chat_id=call.from_user.id, message_id=call.message.id,
                                          text=text, parse_mode='markdown', reply_markup=markups)
                except ApiTelegramException:
                    try:
                        bot.delete_message(call.message.chat.id, call.message.message_id)
                        delete = bot.send_message(call.from_user.id, text, reply_markup=markups, parse_mode='markdown')

                        if call.from_user.id in sessions.users:
                            sessions.users[call.from_user.id]['message']['delete'] = delete.id

                    except ApiTelegramException:
                        bot.answer_callback_query(callback_query_id=call.id, text='❎ Действие устарело')
                        bot.send_message(call.from_user.id, texts.menu('user', 'main', user=call.from_user.id),
                                         parse_mode='markdown', reply_markup=buttons.menu('user', 'main'))

            case 'confirm':
                text, markups = str(), str()

                if 'established-data' in call.data:
                    comeback = 'main'
                    match queries[-1]:
                        case 'instagram':
                            comeback = 'parsing'

                    if call.from_user.id in sessions.users.keys():
                        data = sessions.users[call.from_user.id]['actions']['data']

                        match data['type']:
                            case 'instagram':
                                login = cryptor.encrypt(data['login'])
                                password = cryptor.encrypt(data['password'], login['secret'])
                                secret = cryptor.encrypt(password['secret'])

                                database.change_data('users', 'login', login['data'], call.from_user.id)
                                database.change_data('users', 'password', password['data'], call.from_user.id)
                                database.change_data('users', 'secret', secret['data'], call.from_user.id)

                                keys = handler.file('read', 'keys')
                                keys[call.from_user.id] = secret['secret']
                                handler.file('write', 'keys', keys)

                                bot.edit_message_text(
                                    chat_id=call.from_user.id, message_id=call.message.id,
                                    text=texts.success('established-instagram-data'), parse_mode='markdown')

                                match data['route']:
                                    case 'parsing':
                                        data = sessions.users[call.from_user.id]['actions']['data']
                                        login, password = data['login'], data['password']
                                        delete = bot.send_message(
                                            call.from_user.id, texts.processes('user', 'parse-pages', step=1),
                                            parse_mode='markdown', reply_markup=buttons.cancel_reply('анализ страниц'))
                                        sessions.reset(
                                            'user', call.from_user.id, 'parse-pages', message=call.message.id)

                                        sessions.users[call.from_user.id]['message']['delete'] = delete.id
                                        sessions.users[call.from_user.id]['actions']['data']['login'] = login
                                        sessions.users[call.from_user.id]['actions']['data']['password'] = password

                                    case 'settings':
                                        print('route to settins')

                    else:
                        match comeback:
                            case 'main':
                                text = texts.menu('user', 'main', user=call.from_user.id)
                                markups = buttons.menu('user', 'main')
                            case 'parsing':
                                text = texts.menu('user', 'parsing', user=call.from_user.id)
                                markups = buttons.menu('user', 'parsing', user=call.from_user.id)

                        bot.answer_callback_query(callback_query_id=call.id, text='❎ Действие устарело')
                        bot.send_message(call.from_user.id, text, parse_mode='markdown', reply_markup=markups)

            case 'set':
                if 'instagram-data' in call.data:
                    mode = call.data.replace(f'-{queries[-1]}', '')
                    sessions.start(call.from_user.id, 'user', 'set-data', call.message.id)
                    sessions.users[call.from_user.id]['actions']['data']['route'] = queries[-1]
                    sessions.users[call.from_user.id]['actions']['data']['type'] = 'instagram'
                    sessions.users[call.from_user.id]['actions']['step'] += 1

                    bot.delete_message(call.from_user.id, call.message.id)
                    delete = bot.send_message(call.from_user.id, text=texts.processes('user', mode, step=1),
                                              parse_mode='markdown', reply_markup=buttons.cancel_reply('ввод данных'))

                    sessions.users[call.from_user.id]['message']['delete'] = delete.id


    try:
        bot.infinity_polling()
    except Exception as error:
        path, file = 'logs/', f"log-{datetime.now().strftime('%d.%m.%Y-%H:%M:%S')}.txt"

        logging.basicConfig(filename=f"{path}{file}", level=logging.ERROR)
        logging.error(error, exc_info=True)


