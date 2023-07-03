import itertools
import sqlite3
from matplotlib import pyplot as plt
from PIL import Image
import requests
import telebot
import conf
import threading
lock = threading.Lock()
import re
from nltk.stem import WordNetLemmatizer
import pymorphy2
morph = pymorphy2.MorphAnalyzer()
from telebot import types
lemmatizer = WordNetLemmatizer()
import emoji
import random
import flask
import logging

logger = telebot.logger
telebot.logger.setLevel(logging.DEBUG)

conn = sqlite3.connect('main5.db', check_same_thread=False, timeout=10)
cur = conn.cursor()

WEBHOOK_URL_BASE = "https://{}:{}".format(conf.WEBHOOK_HOST, conf.WEBHOOK_PORT)
WEBHOOK_URL_PATH = "/{}/".format(conf.TOKEN)

bot = telebot.TeleBot(conf.TOKEN, parse_mode='HTML', threaded=False)

bot.remove_webhook()

bot.set_webhook(url=WEBHOOK_URL_BASE+WEBHOOK_URL_PATH)

app = flask.Flask(__name__)

def get_clean(text):
    text = re.sub(r"[^а-яА-Я?.!¿]+", " ", text)
    text = re.sub(r"http\S+", "",text)
    text = re.sub(r"http", "",text)
    html=re.compile(r'<.*?>')
    text = html.sub(r'',text)
    punctuations = '@#!?+&*[]-%.:/();$=><|{}^' + "'`" + '_'
    for p in punctuations:
        text = text.replace(p,'')
    text = [word.lower() for word in text.split()]
    text = [morph.normal_forms(word)[0] for word in text]
    text = [lemmatizer.lemmatize(word) for word in text]
    text = " ".join(text)
    emoji_pattern = re.compile("["
                            u"\U0001F600-\U0001F64F"
                            u"\U0001F300-\U0001F5FF"
                            u"\U0001F680-\U0001F6FF"
                            u"\U0001F1E0-\U0001F1FF"
                            u"\U00002702-\U000027B0"
                            u"\U000024C2-\U0001F251"
                            "]+", flags=re.UNICODE)
    text = emoji_pattern.sub(r'', text)
    return text

def user_query(products, absent, category, cuisine):
    common = ['сахар', 'соль', 'оливковое масло', 'сода', 'уксус', 'растительное масло', 'зелень', 'ванилин', 'сливочное масло','чеснок','вода']
    prod = []
    result = {}
    out_of_filters = {}
    for product in products:
        cleaned_product = get_clean(product)
        cleaned_product = cleaned_product.split()
        product2 = ''
        prod.append(cleaned_product)
        if len(cleaned_product) != 1:
            for word in cleaned_product:
                noun_check = morph.parse(word)[0]
                if noun_check.tag.POS == 'NOUN':
                    product2 = word
                    break
        else:
            product2 = cleaned_product[0]
        if product2 not in common:
            with lock:
                result[product2] = list(itertools.chain(*cur.execute(f"select id from ingredients where ingredient like '%{product2}%'").fetchall()))
            if len(category) > 1 and len(cuisine) > 1:
                new_id = []
                for id in result[product2]:
                    try:
                        category_of_id = cur.execute(f"select * from main where id = '{id}'").fetchone()[2]
                        cuisine_of_id = cur.execute(f"select * from main where id = '{id}'").fetchone()[3]
                    except:
                        category_of_id = str(); cuisine_of_id = str()
                    if len(category_of_id) > 1 and category_of_id != 'передумал(а)' and len(cuisine) > 1 and 'передумал(а)' not in cuisine:
                        if category_of_id == category and cuisine_of_id[:-6] == cuisine:
                            new_id.append(id)
                    elif (len(category) > 1 and 'передумал(а)' not in category) and (len(cuisine) < 1 or 'передумал(а)' in cuisine):
                        if category_of_id == category:
                            new_id.append(id)
                    elif (len(category) < 1 or 'передумал(а)' in category) and (len(cuisine) < 1 or 'передумал(а)' in cuisine):
                        if cuisine_of_id[:-6] == cuisine:
                            new_id.append(id)
                    else:
                        new_id.append(id)
                result[product2] = new_id
            out_of_filters[product2] = list(itertools.chain(*cur.execute(f"select id from ingredients where ingredient like '%{product2}%'").fetchall()))

    keys = list(result.keys())
    intersection_all = str()
    if len(keys) == 1:
        intersection_all = result[keys[0]]
    else:
        for n in range(len(keys)-1):
            intersection = list(set(result[keys[n]]) & set(result[keys[n+1]]))
            if intersection_all != '':
                intersection_all = list(set(intersection) & set(intersection_all))
            else:
                intersection_all = intersection
    id_absent = {}
    id_remove = []

    if absent != '-':
        for item in absent:
            with lock:
                id_absent[item] = list(itertools.chain(*cur.execute(f"select id from ingredients where ingredient like '%{item}%'").fetchall()))
        for key in id_absent.keys():
            for a in list(set(intersection_all) & set(id_absent[key])):
                id_remove.append(a)
        intersection_all = list(set(intersection_all))
        for element in list(set(id_remove)):
            intersection_all.remove(element)

    conclusion1 = []
    conclusion2 = []
    conclusion3 = []
    recommendations = []
    flag = 0
    for id in intersection_all:
        structure = cur.execute(f"select ingredients from main where id = '{id}'").fetchone()
        need_to_have = 0
        for a in structure[0].split(','):
            for b in keys:
                if b in a:
                    flag = 1
            for b in common:
                if b in a:
                    flag = 1
            if flag == 0:
                need_to_have += 1
            flag = 0

        if need_to_have == 0:
            conclusion1.append(id)
        elif need_to_have == 1:
            conclusion2.append(id)
        elif need_to_have == 2:
            conclusion3.append(id)
        else:
            if len(recommendations) < 10:
                recommendations.append(id)

    result1 = {}
    result2 = {}
    result3 = {}
    result4 = {}
    for id in conclusion1:
        name = cur.execute(f"select name from main where id = '{id}'").fetchone()
        name = name[0].split(',')[0]
        result1[name] = id
    for id in conclusion2:
        name = cur.execute(f"select name from main where id = '{id}'").fetchone()
        name = name[0].split(',')[0]
        result2[name] = id
    for id in conclusion3:
        name = cur.execute(f"select name from main where id = '{id}'").fetchone()
        name = name[0].split(',')[0]
        result3[name] = id
    for id in recommendations:
        name = cur.execute(f"select name from main where id = '{id}'").fetchone()
        name = name[0].split(',')[0]
        result4[name] = id

    result5 = {}
    reccomend_out_of_filters = []
    for product in out_of_filters.keys():
        for id in out_of_filters[product]:
            structure = cur.execute(f"select ingredients from main where id = '{id}'").fetchone()
            need_to_have = 0
            for a in structure[0].split(','):
                for b in keys:
                    if b in a:
                        flag = 1
                for b in common:
                    if b in a:
                        flag = 1
                if flag == 0:
                    need_to_have += 1
                flag = 0
            if need_to_have <= 5:
                reccomend_out_of_filters.append(id)
    n = int()
    for id in reccomend_out_of_filters:
        if n >= 10:
            break
        else:
            n += 1
            name = cur.execute(f"select name from main where id = '{id}'").fetchone()
            name = name[0].split(',')[0]
            result5[name] = id

    return [result1, result2, result3, result4, result5]

def user_choice(id):
    row = list(itertools.chain(*cur.execute(f"select * from main where id = '{id}'").fetchall()))
    steps = row[5].split(' ;')
    images = row[6].split(' ;')
    columns = 3
    n = 0
    rows = len(steps)/3
    if round(rows) != rows:
        rows = int(rows) + 1
    else:
        rows = int(rows)
    size = (30,len(images)*rows)
    fig = plt.figure(figsize=size)
    for url in images:
        n += 1
        im = Image.open(requests.get(url, stream=True).raw)
        fig.add_subplot(rows, columns, n)
        plt.imshow(im)
        plt.axis('off')
        plt.title(n, fontdict = {'fontsize' : 30})
    row[1] = row[1].replace(u'\xa0', u' ')
    plt.savefig(f'{row[1]}.jpeg')
    photo_name = f'{row[1]}.jpeg'
    return photo_name

categories = cur.execute("select category from main").fetchall()
buttons_categories = []
for a in set(categories):
    a = str(a)[2:-3]
    buttons_categories.append(a)
buttons_categories = sorted(buttons_categories)
buttons_categories.append('передумал(а)')

def cuisines(category):
    if len(category) > 1 and category != 'передумал(а)':
        cuisines = cur.execute(f"select cuisine from main where category LIKE '%{category}%'").fetchall()
    else:
        cuisines = cur.execute(f"select cuisine from main").fetchall()
    buttons_cuisines = []
    for a in set(cuisines):
        if 'кухня' in str(a):
            a = str(a)[2:-9]
        else:
            a = str(a)[2:-3]
        buttons_cuisines.append(a)
    buttons_cuisines = sorted(buttons_cuisines)
    buttons_cuisines.append('передумал(а)')
    return buttons_cuisines

buttons_cuisines = cuisines('')

def keyboard_options(direction, options, i):
    keyboard = types.InlineKeyboardMarkup(row_width=4)
    buttons_added = []

    if options == buttons_categories:
        name = 'CATEGORYswitch'
    elif set(options).issubset(buttons_cuisines):
        name = 'CUISINEswitch'

    if direction == 'none':
        if len(options)-1 > i+1:
            buttons_added.append(telebot.types.InlineKeyboardButton(text=options[i], callback_data=options[i]))
            buttons_added.append(telebot.types.InlineKeyboardButton(text=options[i+1], callback_data=options[i+1]))
            buttons_added.append(telebot.types.InlineKeyboardButton(text=emoji.emojize('➡'), callback_data=f'{name}Next_{i+1}'))
        elif len(options)-1 == i+1:
            buttons_added.append(telebot.types.InlineKeyboardButton(text=options[i], callback_data=options[i]))
            buttons_added.append(telebot.types.InlineKeyboardButton(text=options[i+1], callback_data=options[i+1]))
        elif len(options)-1 == i:
            buttons_added.append(telebot.types.InlineKeyboardButton(text=options[i], callback_data=options[i]))

    elif direction == 'next':
        if len(options)-1 > i+2:
            buttons_added.append(telebot.types.InlineKeyboardButton(text=emoji.emojize('⬅'), callback_data=f'{name}Back_{i+1}'))
            buttons_added.append(telebot.types.InlineKeyboardButton(text=options[i+1], callback_data=options[i+1]))
            buttons_added.append(telebot.types.InlineKeyboardButton(text=options[i+2], callback_data=options[i+2]))
            buttons_added.append(telebot.types.InlineKeyboardButton(text=emoji.emojize('➡'), callback_data=f'{name}Next_{i+2}'))
        elif len(options)-1 == i+2:
            buttons_added.append(telebot.types.InlineKeyboardButton(text=emoji.emojize('⬅'), callback_data=f'{name}Back_{i+1}'))
            buttons_added.append(telebot.types.InlineKeyboardButton(text=options[i+1], callback_data=options[i+1]))
            buttons_added.append(telebot.types.InlineKeyboardButton(text=options[i+2], callback_data=options[i+2]))
        elif len(options)-1 == i+1:
            buttons_added.append(telebot.types.InlineKeyboardButton(text=emoji.emojize('⬅'), callback_data=f'{name}Back_{i+1}'))
            buttons_added.append(telebot.types.InlineKeyboardButton(text=options[i+1], callback_data=options[i+1]))

    elif direction == 'back':
        if i- 2 > 0:
            buttons_added.append(telebot.types.InlineKeyboardButton(text=emoji.emojize('⬅'), callback_data=f'{name}Back_{i-2}'))
            buttons_added.append(telebot.types.InlineKeyboardButton(text=options[i-2], callback_data=options[i-2]))
            buttons_added.append(telebot.types.InlineKeyboardButton(text=options[i-1], callback_data=options[i-1]))
            buttons_added.append(telebot.types.InlineKeyboardButton(text=emoji.emojize('➡'), callback_data=f'{name}Next_{i-1}'))
        elif i-2 == 0:
            buttons_added.append(telebot.types.InlineKeyboardButton(text=options[i-2], callback_data=options[i-2]))
            buttons_added.append(telebot.types.InlineKeyboardButton(text=options[i-1], callback_data=options[i-1]))
            buttons_added.append(telebot.types.InlineKeyboardButton(text=emoji.emojize('➡'), callback_data=f'{name}Next_{i-1}'))
        elif i-1 == 0:
            buttons_added.append(telebot.types.InlineKeyboardButton(text=options[i-1], callback_data=options[i-1]))
            buttons_added.append(telebot.types.InlineKeyboardButton(text=emoji.emojize('➡'), callback_data=f'{name}Next_{i-1}'))

    if buttons_added:
        keyboard.add(*buttons_added)

    return keyboard

def get_ingridients(input):
    try:
        with open('category.txt', 'r', encoding='UTF-8') as f:
            category = next(f).strip()
        with open('cuisine.txt', 'r', encoding='UTF-8') as f:
            cuisine = next(f).strip()
    except:
        category = ''; cuisine = ''
    keyboard = types.InlineKeyboardMarkup(row_width=5)
    buttons = []
    reply = str()
    try:
        if ';' in input:
            absent = input.split(';')[1]
            ingridients = input.split(';')[0].split(',')
        else:
            absent = '-'
            ingridients = input.split(',')
        with open('reccom.txt', 'w', encoding='UTF-8') as f:
            print(f'{absent}-{ingridients}', file=f)
        result = user_query(ingridients, absent, category, cuisine)
        count = 0
        recommendations = str()
        while True:
            if len(result[0].keys()) > 0:
                for key in result[0].keys():
                    if count == 10:
                        break
                    else:
                        if list(result[0].keys()).index(key) == 0:
                            reply += 'Ниже блюда, которые можно приготовить:\n'
                        count += 1
                        reply += f'{count}) {key}\n'
                        buttons.append(types.InlineKeyboardButton(text=str(count), callback_data=result[0][key]))
            else:
                reply += 'К сожалению, количество продуктов или их сочетание не позволяет подобрать для Вас блюдо\n'

            for key in result[1].keys():
                if count == 10:
                    break
                else:
                    if list(result[1].keys()).index(key) == 0:
                        reply += 'Ниже блюда, которые можно приготовить, если докупить 1 продукт:\n'
                    count += 1
                    reply += f'{count}) {key}\n'
                    buttons.append(types.InlineKeyboardButton(text=str(count), callback_data=result[1][key]))
            for key in result[2].keys():
                if count == 10:
                    break
                else:
                    if list(result[2].keys()).index(key) == 0:
                        reply += 'Ниже блюда, которые можно приготовить, если докупить 2 продукта:\n'
                    count += 1
                    reply += f'{count}) {key}\n'
                    buttons.append(types.InlineKeyboardButton(text=str(count), callback_data=result[2][key]))
            with open('bt.txt', 'w', encoding='UTF-8') as f:
                print([result,count], file=f)
            if len(result[3].keys()) > 0:
                recommendations = '<b>Рекомендации</b>\n'
                for key in result[3].keys():
                    if count == 10:
                        break
                    else:
                        count += 1
                        recommendations += f'{count}) {key}\n'
                        buttons.append(types.InlineKeyboardButton(text=str(count), callback_data=result[3][key]))

            else:
                recommendations = '<b>Рекомендации вне фильтров</b>\n'
                recommendations += 'Похоже, что введенные продукты редко встречаются в блюдах выбранных категорий. Ниже блюда, в которых частично содержатся Ваши продукты:\n'
                for key in result[4].keys():
                    if count == 10:
                        break
                    else:
                        count += 1
                        recommendations += f'{count}) {key}\n'
                        buttons.append(types.InlineKeyboardButton(text=str(count), callback_data=result[4][key]))
            keyboard.add(*buttons)
            break

        return [keyboard, reply, recommendations]

    except:
        reply = 'Некорректный запрос'
        return [reply]

def random_suggestion(category,cuisine):
    if category != 'передумал(а)' and cuisine != 'передумал(а)':
        dishes = cur.execute(f"select * from main where category LIKE '%{category}%' AND cuisine LIKE '%{cuisine}%'").fetchall()
    elif category == 'передумал(а)' and cuisine != 'передумал(а)':
        dishes = cur.execute(f"select * from main where cuisine LIKE '%{cuisine}%'").fetchall()
    elif category != 'передумал(а)' and cuisine == 'передумал(а)':
        dishes = cur.execute(f"select * from main where category LIKE '%{category}%'").fetchall()
    else:
        dishes = cur.execute(f"select * from main").fetchall()
    ids = []
    for id in dishes:
        ids.append(id[0])
    if len(dishes) > 0:
        info = random.choice(dishes)
        reply = str()
        reply += f'<b>НАЗВАНИЕ:</b> {info[1]}\n' + f'\n<b>ИНГРЕДИЕНТЫ:</b> {info[4]}\n'
        steps = '\n'.join(info[5].split(';'))
        reply += '\n' + steps
        return [info[0], reply, len(dishes), ids]
    else:
        reply = 'К сожалению, таких сочетаний не найдено'
        return [reply]

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    keyboard = telebot.types.ReplyKeyboardMarkup()
    keyboard.row('Твои предложения')
    keyboard.row('Подбери блюдо')
    keyboard.row('Главное')
    bot.send_message(message.chat.id,
                    emoji.emojize('Привет! Я бот, который советует вкусную еду 😊\n'\
                    '\n'\
                    'Если ты нажмешь на кнопку “твои предложения”, я расскажу тебе о всех блюдах, о которых знаю, а именно покажу тебе их рецепты!'\
                    'Эта кнопка нужна тебе, если ты совсем не знаешь, что приготовить.'\
                    '\n'\
                    '\nЕсли же у тебя в холодильнике затесался старый огурец и пара других вещиц, тебе нужна кнопка “подбери блюдо”!'\
                    '\nЯ внимательно изучу твои запасы и подумаю, что рациональнее всего будет приготовить. Продукты нужно вводить строго через запятую без пробелов, так я смогу оперативно найти информацию и спасу твой завтрак, обед или, может, ужин.'\
                    '\n'\
                    '\nЯ по умолчанию думаю, что у тебя есть следующие штуки: <i>сахар,соль,оливковое масло,растительное масло,зелень,ванилин,сливочное масло,чеснок,мука</i>.'\
                    '\nЕсли что-то из перечисленного закончилось, пожалуйста, скажи мне об этом.'\
                    '\n'\
                    '\n<b>Формат ввода продуктов следующий</b>: <i>творог,сметана,куриное яйцо,сахар,изюм,манная крупа,ванилин,ягодный сироп;растительное масло</i>, '\
                    'где продукты до знака <i>;</i> - продукты, которые у Вас есть, а после - продукты из списка по умолчанию, которых у Вас нет. Если у Вас есть всё из представленного списка, точку с запятой игнорируйте'\
                    '\nПродукты вводите без пробелов. Обрати внимание, что после точки с запятой могут идти только продукты из моего списка! Я проверяю их отсутствие'\
                    '\n'\
                    '\nP.S.Многие рецепты сопровождаются фотографиями, но они могут приходить с небольшой задержкой.'\
                    '\n<b>С чего начнём?</b>'), reply_markup=keyboard)
    bot.register_next_step_handler(message, step1)

@bot.message_handler(content_types = ['text'])
def step1(message):
    if message.text == 'Главное':
        send_welcome(message)
    elif message.text == 'Твои предложения':
        open('random.txt', 'w').close(); open('change.txt', 'w').close()
        buttons = [
            [
                telebot.types.InlineKeyboardButton(text='Случайное блюдо', callback_data='SUGrandom'),
                telebot.types.InlineKeyboardButton(text='Настроить категории', callback_data='SUGfilter'),
            ],
        ]
        keyboard = types.InlineKeyboardMarkup(buttons)
        bot.send_message(message.from_user.id, 'Начну поиск, как только уточну некоторые детали...', reply_markup=keyboard)
    elif message.text == 'Подбери блюдо':
        open('random.txt', 'w').close(); open('change.txt', 'w').close()
        N = bot.send_message(message.from_user.id,'Введите продукты:')
        bot.register_next_step_handler(N, fit2)
    elif message.text not in buttons_categories and message.text not in buttons_cuisines:
            bot.register_next_step_handler(message, fit2)


def fit2(call):
    if len(call.text) != 0 and call.text != 'Твои предложения':
        with open('products.txt', 'w', encoding='UTF-8') as f:
            print(call.text, file=f)
        buttons = [
                    [
                        telebot.types.InlineKeyboardButton(text='Да', callback_data='FITда'),
                        telebot.types.InlineKeyboardButton(text='Нет', callback_data='FITнет'),
                    ],
                ]
        keyboard = types.InlineKeyboardMarkup(buttons)
        bot.send_message(call.from_user.id,'Хотите ли Вы использовать фильтр (выбрать кухню и(или) категорию)?', reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == 'FITда' or call.data == 'FITнет')
def fit3(call):
    if call.data == 'FITда':
        keyboard = keyboard_options('none', buttons_categories, 0)
        bot.send_message(call.from_user.id, 'Я хочу, чтобы блюдо было из следующей категории...', reply_markup=keyboard)

    elif call.data == 'FITнет':
        with open('products.txt', 'r', encoding='UTF-8') as f:
            products = next(f).strip()
        open('category.txt', 'w').close(); open('cuisine.txt', 'w').close()
        result = get_ingridients(products)
        if len(result) == 1:
            bot.send_message(call.from_user.id, text=result[0], reply_markup=result[0])
        elif 'К сожалению, количество продуктов или их сочетание не позволяет подобрать для Вас блюдо' in result[1]:
            output = result[1] + '\n' + result[2]
            bot.send_message(call.from_user.id, text=output, reply_markup=result[0])
        else:
            bot.send_message(call.from_user.id, text=result[1], reply_markup=result[0])
        with open('products.txt', 'w', encoding='UTF-8') as f:
            print('', file=f)

@bot.callback_query_handler(func=lambda call: call.data == 'SUGrandom' or call.data == 'SUGfilter' or call.data == 'change_random' or call.data == 'change_filter')
def suggest_smth(call):
    if call.data == 'SUGrandom' or call.data == 'change_random' or call.data == 'change_filter':
        if call.data == 'change_filter':
            with open('random.txt', 'r', encoding='UTF-8') as f:
                change_filter_params = f.read()
            category = change_filter_params.split(';')[1]; cuisine = change_filter_params.split(';')[2]
            result = random_suggestion(category,cuisine)
            if len(result) == 1:
                bot.send_message(call.from_user.id, text=result[0])

            else:
                dish = cur.execute(f"select * from main where id = '{result[0]}'").fetchone()
                images = dish[6]
                if result[2] > 1:
                    keyboard = types.InlineKeyboardMarkup(); keyboard.add(telebot.types.InlineKeyboardButton(text='Меняй', callback_data='change_filter'))
                    bot.send_message(call.from_user.id, text=result[1], reply_markup=keyboard)
                else:
                    bot.send_message(call.from_user.id, text=result[1])
                try:
                    if len(images) >1:
                        name_file = user_choice(dish[0])
                        bot.send_photo(call.from_user.id, photo=open(name_file,'rb'))
                except Exception as e:
                    error = e
        else:
            result = random_suggestion('','')
            if len(result) == 1:
                bot.send_message(call.from_user.id, text=result[0])

            else:
                dish = cur.execute(f"select * from main where id = '{result[0]}'").fetchone()
                images = dish[6]
                if result[2] > 1:
                    keyboard = types.InlineKeyboardMarkup(); keyboard.add(telebot.types.InlineKeyboardButton(text='Меняй', callback_data='change_random'))
                    bot.send_message(call.from_user.id, text=result[1], reply_markup=keyboard)
                else:
                    bot.send_message(call.from_user.id, text=result[1])
                try:
                    if len(images) >1:
                        name_file = user_choice(dish[0])
                        bot.send_photo(call.from_user.id, photo=open(name_file,'rb'))
                except Exception as e:
                    error = e

    elif call.data == 'SUGfilter':
        with open('random.txt', 'w', encoding='UTF-8') as f:
            print('Yes', file=f)
        keyboard = keyboard_options('none', buttons_categories, 0)
        bot.send_message(call.from_user.id, 'Я хочу, чтобы блюдо было из следующей категории...', reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data in buttons_categories or 'CATEGORYswitch' in call.data)
def step2(call):

    if 'CATEGORYswitchNext' in call.data:
        i = int(call.data.split('_')[1])
        keyboard = keyboard_options('next', buttons_categories, i)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text='Я хочу, чтобы блюдо было из следующей категории...',
        reply_markup=keyboard)

    elif 'CATEGORYswitchBack' in call.data:
        i = int(call.data.split('_')[1])
        keyboard = keyboard_options('back', buttons_categories, i)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text='Я хочу, чтобы блюдо было из следующей категории...',
        reply_markup=keyboard)

    else:
        with open('random.txt', 'r', encoding='UTF-8') as f:
            random_dish = f.read()
        if 'Yes' in random_dish:
            if ';' not in random_dish:
                with open('random.txt', 'a', encoding='UTF-8') as f:
                    f.write(f';{call.data}')
            buttons = cuisines(call.data)
            keyboard = keyboard_options('none', buttons, 0)
            bot.answer_callback_query(callback_query_id=call.id, text='Выберите кухню', show_alert=False)
            bot.send_message(call.from_user.id, 'Я хочу, чтобы блюдо было из следующей кухни...', reply_markup=keyboard)
        else:
            with open('category.txt', 'w', encoding='UTF-8') as f:
                print(call.data, file=f)
            buttons = cuisines(call.data)
            keyboard = keyboard_options('none', buttons, 0)
            bot.answer_callback_query(callback_query_id=call.id, text='Выберите кухню', show_alert=False)
            bot.send_message(call.from_user.id, 'Я хочу, чтобы блюдо было из следующей кухни...', reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data in buttons_cuisines or 'CUISINEswitch' in call.data)
def step4(call):
    bot.answer_callback_query(callback_query_id=call.id, show_alert=False)
    if 'CUISINEswitchNext' in call.data:
        i = int(call.data.split('_')[1])
        with open('random.txt', 'r', encoding='UTF-8') as f:
            random_dish = f.read()
        if 'Yes' in random_dish:
            random_dish = random_dish.split(';')[1]
            buttons = cuisines(random_dish)
            keyboard = keyboard_options('next', buttons, i)
        else:
            with open('category.txt', 'r', encoding='UTF-8') as f:
                category = f.read()
            buttons = cuisines(category[len(category)-2])
            keyboard = keyboard_options('next', buttons, i)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text='Я хочу, чтобы блюдо было из следующей кухни...',
        reply_markup=keyboard)

    elif 'CUISINEswitchBack' in call.data:
        i = int(call.data.split('_')[1])
        with open('random.txt', 'r', encoding='UTF-8') as f:
            random_dish = f.read()
        if 'Yes' in random_dish:
            random_dish = random_dish.split(';')[1]
            buttons = cuisines(random_dish)
            keyboard = keyboard_options('back', buttons, i)
        else:
            with open('category.txt', 'r', encoding='UTF-8') as f:
                category = f.read()
            buttons = cuisines(buttons)
            keyboard = keyboard_options('back', buttons, i)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text='Я хочу, чтобы блюдо было из следующей кухни...',
        reply_markup=keyboard)

    else:
        with open('random.txt', 'r', encoding='UTF-8') as f:
            random_dish = f.read()
        if 'Yes' in random_dish:
            category = random_dish.split(';')[1]
            result = random_suggestion(category,call.data)
            if random_dish.count(';') <= 1:
                with open('random.txt', 'w', encoding='UTF-8') as f:
                    f.write(f'Yes;{category};{call.data}')
            if len(result) == 1:
                bot.send_message(call.from_user.id, text=result[0])
            else:
                dish = cur.execute(f"select * from main where id = '{result[0]}'").fetchone()
                images = dish[6]
                if result[2] > 1:
                    keyboard = types.InlineKeyboardMarkup(); keyboard.add(telebot.types.InlineKeyboardButton(text='Меняй', callback_data='change_filter'))
                    bot.send_message(call.from_user.id, text=result[1], reply_markup=keyboard)
                else:
                    bot.send_message(call.from_user.id, text=result[1])
                try:
                    if len(images) >1:
                        name_file = user_choice(dish[0])
                        bot.send_photo(call.from_user.id, photo=open(name_file,'rb'))
                except Exception as e:
                    error = e
        else:
            with open('cuisine.txt', 'w', encoding='UTF-8') as f:
                print(call.data, file=f)
            with open('products.txt', 'r', encoding='UTF-8') as f:
                products = next(f).strip()
            result = get_ingridients(products)
            if len(result) == 1:
                bot.send_message(call.from_user.id, text=result[0], reply_markup=result[0])
            elif 'К сожалению, количество продуктов или их сочетание не позволяет подобрать для Вас блюдо' in result[1]:
                output = result[1] + '\n' + result[2]
                bot.send_message(call.from_user.id, text=output, reply_markup=result[0])
            else:
                bot.send_message(call.from_user.id, text=result[1], reply_markup=result[0])
            with open('products.txt', 'w', encoding='UTF-8') as f:
                print('', file=f)

@bot.callback_query_handler(func=lambda call: type(int(call.data)) == int)
def output(call):
    bot.answer_callback_query(callback_query_id=call.id, show_alert=False)
    dish = cur.execute(f"select * from main where id = '{call.data}'").fetchone()
    reply = str()
    reply += f'<b>НАЗВАНИЕ:</b> {dish[1]}\n' + f'\n<b>ИНГРЕДИЕНТЫ:</b> {dish[4]}\n'
    steps = '\n'.join(dish[5].split(';'))
    reply += '\n' + steps
    bot.send_message(call.from_user.id, text=reply)
    images = dish[6]
    try:
        if len(images) >1:
            name_file = user_choice(dish[0])
            bot.send_photo(call.from_user.id, photo=open(name_file,'rb'))
    except Exception as e:
        error = e

if __name__ == '__main__':
    bot.polling(none_stop=True)

@app.route(WEBHOOK_URL_PATH, methods=['POST'])
def webhook():
    if flask.request.headers.get('content-type') == 'application/json':
        json_string = flask.request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        flask.abort(403)