import bot as bot_processor
from core import Configs, Sessions, Processes, Database, Driver, Cryptor, Handler, Texts, Buttons
from telebot import TeleBot
from threading import Thread

if __name__ == '__main__':
    configs_processor = Configs()
    configs = configs_processor.initialization()
    database = Database(configs)
    print(configs)

    bot = TeleBot(configs['bot']['token'])
    handler = Handler(configs, database)
    driver = Driver()
    cryptor = Cryptor(handler)

    texts = Texts(configs, database, handler)
    buttons = Buttons(configs, database, handler)

    sessions = Sessions()
    processes = Processes(bot, texts, buttons)

    thread_bot = Thread(target=bot_processor.run,
                        args=(bot, configs, sessions, database, driver, cryptor, handler, texts, buttons))
    thread_processes = Thread(target=processes.run)

    thread_bot.start()
    thread_processes.start()


