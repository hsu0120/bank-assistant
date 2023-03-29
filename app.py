import os
import re
import openai
import datetime
from firebase import firebase
from flask import Flask, request

import requests
from bs4 import BeautifulSoup

from facebookbot import (
    FacebookBotApi, WebhookHandler
)

from facebookbot.models import (
    TextMessage, ImageMessage, VideoMessage, AudioMessage, 
    FileMessage, AttachmentMessage, LocationMessage, FallbackMessage,
    
    TextMessageEvent, AttachmentMessageEvent, GetStartedEvent, QuickReplyMessageEvent,
    PostbackEvent, LinkingEvent, UnLinkingEvent, TextEchoMessageEvent, AttachmentEchoMessageEvent,
    
    PostbackAction, URLAction, 
    TemplateSendMessage, ButtonsTemplate, GenericTemplate, MediaTemplate, 
    GenericElement, ImageElement, VideoElement,
    
    TextSendMessage, ImageSendMessage, VideoSendMessage, AudioSendMessage, FileSendMessage,
    LocationQuickReply, TextQuickReply,
    PostbackAction, URLAction, 
    ButtonsTemplate, TemplateSendMessage, GenericTemplate, GenericElement, ImageElement, VideoElement
)


# 初始化
app = Flask(__name__)

ACCESS_TOKEN = os.environ.get('PAGE_TOKEN')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
CHATGPT_TOKEN = os.environ.get('CHATGPT_TOKEN')
DB_URL = os.environ.get('DB_URL')

fb_bot_api = FacebookBotApi(ACCESS_TOKEN)

handler = WebhookHandler()

openai.api_key = CHATGPT_TOKEN

database = firebase.FirebaseApplication(DB_URL, None)

data_init = dict({'status': 0, 'last_time': 0, 'conversation_log': [], 'bert_input': '[CLS}', 'try': 0, 'last_status': 0, 'foreign_currency': ''})
data = dict()

# chatgpt 判斷
def banking(text):
    result = openai.Completion.create(
        model = 'text-davinci-003',
        prompt = f'The following is a statement and the category it falls into:banking, non-banking\n\n{text}\nCategory:',
        temperature = 0,
        max_tokens = 6,
        top_p = 1,
        frequency_penalty = 0,
        presence_penalty = 0
    )['choices'][0]['text'].replace(' ', '')

    print(result)

    return True if result == 'Banking' else False

def banking_category(text):
    result = openai.Completion.create(
        model = 'text-davinci-003',
        prompt = 'The following is a statement and the category it falls into: ' \
                 'greeting, credit card, foreign currency, exchange rate, card loan, house loan, loan, deposit, investment, branch' \
                f'\n\n{text}\nCategory: ',
        temperature = 0,
        max_tokens = 6,
        top_p = 1,
        frequency_penalty = 0,
        presence_penalty = 0
    )['choices'][0]['text'].replace(' ', '')
    print(result)
    return result

def foreign_currency(text):
    response = openai.ChatCompletion.create(
      model="gpt-3.5-turbo",
      messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Summarize the currency in the following statement, if missing or not provide reply No, else reply only the currency abbreviation in three English letters :\n\n{text}\n"}
        ]
    )
    result = response.to_dict()['choices'][0]['message']['content']
    print(result)
    return result[:3] if not result.startswith('No') else None

def foreign_currency_transaction(text):
    result = openai.Completion.create(
        model = 'text-davinci-003',
        prompt = f'The following is a statement and the category it falls into: buy_cash, sell_cash, buy_foreign_currency, sell_foreign_currency\n\n{text}\nCategory:',
        temperature = 0,
        max_tokens = 6,
        top_p = 1,
        frequency_penalty = 0,
        presence_penalty = 0
    )['choices'][0]['text'].replace(' ', '', 1).replace(' ', '_')
    return result.lower() if result.startswith('None') else None

def foreign_currency_amount(text):
    response = openai.ChatCompletion.create(
      model="gpt-3.5-turbo",
      messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Summarize the currency abbreviation in three English letters and the amount in the following statement, if currency or amount is missing reply No, else reply as the format currency/amount\n\n{text}\n"}
        ]
    )
    result = response.to_dict()['choices'][0]['message']['content'].replace(' ', '').split('/')
    print(result)
    return result

def exchange_rate_way(text):
    result = openai.Completion.create(
        model = 'text-davinci-003',
        prompt = f'The following is a statement and the category it falls into: single exchange rate, all exchange rate, non-exchange rate\n\n{text}\nCategory:',
        temperature = 0,
        max_tokens = 6,
        top_p = 1,
        frequency_penalty = 0,
        presence_penalty = 0
    )['choices'][0]['text'].replace(' ', '', 1).replace(' ', '_')
    print(result)
    return result.lower() if result.startswith('Non') else None

def house_loan_address(text):
    result = openai.Completion.create(
        model = 'text-davinci-003',
        prompt = f'The following whether is an full address: yes, no\n\n{text}\nResult:',
        temperature = 0,
        max_tokens = 6,
        top_p = 1,
        frequency_penalty = 0,
        presence_penalty = 0
    )['choices'][0]['text'].replace(' ', '')
    print(result)

    return True if not result.startswith('No') else False

def generate_card_information(text):
    response = openai.ChatCompletion.create(
      model="gpt-3.5-turbo",
      messages=[
            {"role": "system", "content": "You are a bank assistant."},
            {"role": "user", "content": f"提供{text}最多五張玉山信用卡，用'卡名:15字的介紹'這個格式回覆"}
        ]
    )
    ans = response.to_dict()['choices'][0]['message']['content']#.split('\n')

    # result = list()
    # for a in ans:
    #     if a == '\n':
    #         continue
    #     tmp = a.replace(' ：', '：').replace('： ', '：').split('：')
    #     print(tmp)
    #     # result.append(GenericElement(title = tmp[0][3:], 
    #     #                              subtitle = tmp[1]
    #     #                              ))
    # print(result)
    return ans

def generate_response(text):
    response = openai.ChatCompletion.create(
      model="gpt-3.5-turbo",
      messages=[
            {"role": "system", "content": "You are a bank assistant."},
            {"role": "user", "content": f"提供玉山銀行20字相關的回答：{text}"}
        ]
    )
    ans = response.to_dict()['choices'][0]['message']['content']

    return ans

# 處理資料
def save_to_database(user_id):
    database.put(f'/user/{user_id}', 'status', data['status'])
    database.put(f'/user/{user_id}', 'last_time', data['last_time'])
    database.put(f'/user/{user_id}', 'bert_input', data['bert_input'])
    database.put(f'/user/{user_id}', 'conversation_log', data['conversation_log'])
    database.put(f'/user/{user_id}', 'try', data['try'])
    database.put(f'/user/{user_id}', 'last_status', data['last_status'])
    database.put(f'/user/{user_id}', 'foreign_currency', data['foreign_currency'])

def set_data(d_dict):
    data['status'] = d_dict['status']
    data['last_time'] = d_dict['last_time']
    data['conversation_log'] = d_dict['conversation_log']
    data['bert_input'] = d_dict['bert_input']
    data['try'] = d_dict['try']
    data['last_status'] = d_dict['last_status']
    data['foreign_currency'] = d_dict['foreign_currency']

def save_data_user(user_id, text, time, u0):
    data_tmp = database.get('/user', f'{user_id}')
    if data_tmp == None:
        set_data(data_init)
    else:
        set_data(data_tmp)
        if time - data['last_time'] > 1800:
            set_data(data_init)

    data['conversation_log'].append('{"role": "user", ' \
                                     f'"content": "{text}"' \
                                     '}')
    data['bert_input'] += f'{u0}{text}^'
    data['last_time'] = int(time)

    print(data)

def save_data_assistant(user_id, response, c0, c1, c2):
    data['conversation_log'].append('{"role": "assistant", ' \
                                             f'"content": "{response}"' \
                                             '}')
    data['bert_input'] += f'{response}{c0}{c1}{c2}^'

    save_to_database(user_id)

    print(data)


# 爬網頁資料
def get_exchange_rate(currency, rate):
    r = requests.get('https://www.esunbank.com.tw/bank/personal/deposit/rate/forex/foreign-exchange-rates')
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'html.parser')
        
        dollar_info = soup.find_all('tr', {'class': currency})[0]
        exchange_rate = dollar_info.find_all('div', {'class': rate})[0].string

    return exchange_rate

def get_exchange_rate_response(currency):
    r = requests.get('https://www.esunbank.com.tw/bank/personal/deposit/rate/forex/foreign-exchange-rates')
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'html.parser')
        
        dollar_info = soup.find_all('tr', {'class': currency})[0]

        chinese = dollar_info.find_all('div', {'class': 'title-item'})[1].string.replace(' ', '').replace('\n', '')

        buy_rate = dollar_info.find_all('div', {'class': 'BBoardRate'})[0].string
        sell_rate = dollar_info.find_all('div', {'class': 'SBoardRate'})[0].string

        message = f'{chinese} {currency} \n\n我要賣{chinese} {currency} - 買匯價: {buy_rate} \n我要買{chinese} {currency} - 賣匯價: {sell_rate}'
        url = f'https://www.esunbank.com.tw/bank/personal/deposit/rate/forex/exchange-rate-chart#currency={currency}'

    return message, url 


# 匯率相關
def exchange_rate_response(user_id):
    response = '請問你要查個別外幣匯率，還是要一次瀏覽多種外幣別呢？'
    
    data['status'] = 6

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    buttons_template_message = TemplateSendMessage(
        template = ButtonsTemplate(
            text = response,
            buttons = [
                URLAction(
                    title = '查看所有幣別匯率',
                    url = 'https://www.esunbank.com.tw/bank/personal/deposit/rate/forex/foreign-exchange-rates',
                    webview_height_ratio = 'full',
                    messenger_extensions = None,
                    fallback_url = None
                ),
                PostbackAction(
                    title = '個別外幣匯率',
                    payload = 'single_exchange_rate'
                )
            ] 
        )
    )
    
    fb_bot_api.push_message(
        user_id, 
        message = buttons_template_message
    )

def exchange_rate_response_currency(user_id):
    response = '你要查詢哪個外幣呢？'

    data['status'] = 6.1

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    fb_bot_api.push_message(
        user_id, 
        message=TextSendMessage(
            text = response,
            quick_replies = [
                TextQuickReply(title = '美元 USD', payload = 'exchange_rate_USD'),
                TextQuickReply(title = '人民幣 CNY', payload = 'exchange_rate_CNY'),
                TextQuickReply(title = '港幣 HKD', payload = 'exchange_rate_HKD'),
                TextQuickReply(title = '日圓 JPY', payload = 'exchange_rate_JPY'),
                TextQuickReply(title = '歐元 EUR', payload = 'exchange_rate_EUR')
            ]         
        )
    )

def exchange_rate_response_all_currency(user_id):
    response = '一次瀏覽多種外幣別，可以直接按下面的按鈕'
    
    data['status'] = 0

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    buttons_template_message = TemplateSendMessage(
        template = ButtonsTemplate(
            text = response,
            buttons = [
                URLAction(
                    title = '查看所有幣別匯率',
                    url = 'https://www.esunbank.com.tw/bank/personal/deposit/rate/forex/foreign-exchange-rates',
                    webview_height_ratio = 'full',
                    messenger_extensions = None,
                    fallback_url = None
                )
            ] 
        )
    )
    
    fb_bot_api.push_message(
        user_id, 
        message = buttons_template_message
    )

def exchange_rate_response_end(user_id, currency):
    response, send_url = get_exchange_rate_response(currency)

    data['status'] = 0

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C21]')

    buttons_template_message = TemplateSendMessage(
        template=ButtonsTemplate(
            text=response,
            buttons=[
                URLAction(
                    title='外匯走勢',
                    url=send_url,
                    webview_height_ratio='full',
                    messenger_extensions=None,
                    fallback_url=None
                ),
                PostbackAction(
                    title='查其他外幣匯率',
                    payload='exchange_rate'
                )
            ]       
        )
    )
    
    fb_bot_api.push_message(
        user_id, 
        message=buttons_template_message
    )


# 外幣相關
def foreign_currency_response(user_id):
    response = '你要換算哪個外幣呢？'
    
    data['status'] = 8

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(
            text = response,
            quick_replies = [
                TextQuickReply(title = '美元 USD', payload = 'foreign_USD'),
                TextQuickReply(title = '人民幣 CNY', payload = 'foreign_CNY'),
                TextQuickReply(title = '港幣 HKD', payload = 'foreign_HKD'),
                TextQuickReply(title = '日圓 JPY', payload = 'foreign_JPY'),
                TextQuickReply(title = '歐元 EUR', payload = 'foreign_EUR')
            ]          
        )
    )

def foreign_currency_response_transaction(user_id, currency):
    response = '請問你是要?'

    data['status'] = 8.1
    data['foreign_currency'] = currency

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    payload_buy_cash = currency + '_buy_cash'
    payload_sell_cash = currency + '_sell_cash'
    payload_buy_foreign = currency + '_buy_foreign_currency'
    payload_sell_foreign = currency + '_sell_foreign_currency'

    fb_bot_api.push_message(
        user_id, 
        message=TextSendMessage(
            text = response,
            quick_replies = [
                TextQuickReply(title = '買現鈔', payload = payload_buy_cash),
                TextQuickReply(title = '賣現鈔', payload = payload_sell_cash),
                TextQuickReply(title = '買即期外幣', payload = payload_buy_foreign),
                TextQuickReply(title = '賣即期外幣', payload = payload_sell_foreign)
            ]          
        )
    )

def foreign_currency_response_amount(user_id, transaction):
    currency = data['foreign_currency'][8:11]
    response = f'你要換多少呢?(請記得輸入幣別喔)\nEx: {currency} 100 或 TWD 1000'

    data['status'] = 8.2
    data['foreign_currency'] = transaction

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    fb_bot_api.push_message(
        user_id, 
        message=TextSendMessage(text = response)
    )

def foreign_currency_response_end(user_id, currency, transaction, ex_currency, ex_amount):
    if transaction == 'buy_cash':
        exchange_rate = get_exchange_rate(currency, 'CashSBoardRate')
    elif transaction == 'sell_cash':
        exchange_rate = get_exchange_rate(currency, 'CashBBoardRate')
    elif transaction == 'buy_foreign_currency':
        exchange_rate = get_exchange_rate(currency, 'SBoardRate')
    else:
        exchange_rate = get_exchange_rate(currency, 'BBoardRate')

    if ex_currency == 'TWD':
        result = round(float(ex_amount) * float(exchange_rate), 2)
    else:
        result = round(float(ex_amount) * (1/ float(exchange_rate)), 2)
        currency = 'TWD'

    date = str(datetime.datetime.now()).split('.')[0]
    response = f'{ex_currency} {ex_amount} = {currency} {result}\n報價時間: {date}'

    data['status'] = 0
    data['try'] = 0
    data['foreign_currency'] = ''

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C21]')

    generic_template_message = TemplateSendMessage(
        template=GenericTemplate(
            elements=[
                GenericElement(
                    title='貨幣換算結果',
                    subtitle='本匯率換算僅供參考，實際成交價依交易時間而定。',
                    buttons=[
                        PostbackAction(title='調整換算金額', payload='foreign_change'),
                        PostbackAction(title='換算其他外幣', payload='foreign_currency')
                    ]
                )
            ]
        )
    )

    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(text = response)
    )

    fb_bot_api.push_message(
        user_id, 
        message = generic_template_message
    ) 


# 信用卡相關
def credit_card_response(user_id):
    response = '請問你喜歡以下哪一種類型的卡片呢? 我將根據你的偏好，立刻推薦適合的卡片'
    
    data['status'] = 13

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(
            text = response,
            quick_replies = [
                TextQuickReply(title = '網購族', payload = 'credit_card_web'),
                TextQuickReply(title = '百貨購物族', payload = 'credit_card_department'),
                TextQuickReply(title = '生活達人族', payload = 'credit_card_life'),
                TextQuickReply(title = '出國旅遊族', payload = 'credit_card_trip'),
                TextQuickReply(title = '聯名卡', payload = 'credit_card_signed')
            ]          
        )
    )

def credit_card_response_end(user_id, text):
    response = '以下是你可能有興趣的信用卡資訊'

    data['status'] = 0

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C21]')

    generic_element = generate_card_information(text)

    # generic_template_message = TemplateSendMessage(
    #     template = GenericTemplate(
    #         elements = generic_element
    #     )
    # )

    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(text = response)
    )

    # fb_bot_api.push_message(
    #     user_id, 
    #     message = generic_template_message
    # )
    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(text = generic_element)
    )

  
# 貸款相關
def loan_response(user_id):
    response = '請問你有哪個貸款的需求？'

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    buttons_template_message = TemplateSendMessage(
        template = ButtonsTemplate(
            text = response,
            buttons = [
                PostbackAction(
                    title = '我有信貸需求',
                    payload = 'card_loan'
                ),
                PostbackAction(
                    title = '我有房貸需求',
                    payload = 'house_loan'
                )
            ] 
        )
    )
    
    fb_bot_api.push_message(
        user_id, 
        message = buttons_template_message
    )

def house_loan_response(user_id):
    response = '你想要申請'

    data['status'] = 2

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(
            text = response,
            quick_replies = [
                TextQuickReply(title = '購屋貸款', payload = 'house_loan_first'),
                TextQuickReply(title = '房屋加值貸款', payload = 'house_loan_add'),
                TextQuickReply(title = '二順位房貸', payload = 'house_loan_second')
            ]          
        )
    )

def house_loan_response_amount(user_id):
    response = '想要貸多少金額呢？（以萬爲單位）\nEX: 300萬，請輸入300'

    data['status'] = 2.1

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(text = response)
    )

def house_loan_response_purpose(user_id):
    response = '你的貸款資金用途'

    data['status'] = 2.2

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(
            text = response,
            quick_replies = [
                TextQuickReply(title = '購屋', payload = 'house_loan_buy'),
                TextQuickReply(title = '一般修繕', payload = 'house_loan_normal_fix'),
                TextQuickReply(title = '商業修繕', payload = 'house_loan_business_fix')
            ]          
        )
    )

def house_loan_response_own(user_id):
    response = '你要申請貸款的房屋所有權人'

    data['status'] = 2.3

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(
            text = response,
            quick_replies = [
                TextQuickReply(title = '本人持有', payload = 'house_loan_mine'),
                TextQuickReply(title = '本人與配偶持有', payload = 'house_loan_both'),
                TextQuickReply(title = '其他', payload = 'house_loan_other')
            ]          
        )
    )

def house_loan_response_address(user_id):
    if data['try'] == 0:
        response = '麻煩告訴我要評估的房屋所在地址，要有縣市和明確的路段喲！'
    else:
        response = '您的住址可能缺少了:「縣」或「市」「路」或「街」「號」，請提供完整的住址，完整的住址至少要有「縣」或「市」，「路」或「街」，「號」，例如：台北市民生東路三段115號'

    data['status'] = 2.4

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(text = response)
    )

def card_loan_response(user_id):
    response = '你的職業是什麼？'

    data['status'] = 3

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(
            text = response,
            quick_replies = [
                TextQuickReply(title = '金融機構', payload = 'card_loan_finance'),
                TextQuickReply(title = '一般企業', payload = 'card_loan_normal'),
                TextQuickReply(title = '公教人員', payload = 'card_loan_civil'),
                TextQuickReply(title = '其他', payload = 'card_loan_other')
            ]
        )
    )

def card_loan_response_salary(user_id):
    response = '你的年收入大概是多少？'

    data['status'] = 3.1

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(
            text = response,
            quick_replies = [
                TextQuickReply(title = '0', payload = 'card_loan_0'),
                TextQuickReply(title = '20萬以下', payload = 'card_loan_20'),
                TextQuickReply(title = '21-40萬', payload = 'card_loan_40'),
                TextQuickReply(title = '41-60萬', payload = 'card_loan_60'),
                TextQuickReply(title = '61-80萬', payload = 'card_loan_80'),
                TextQuickReply(title = '80-100萬', payload = 'card_loan_100'),
                TextQuickReply(title = '100-200萬', payload = 'card_loan_200'),
                TextQuickReply(title = '200萬以上', payload = 'card_loan_above')
            ]
        )
    )

def card_loan_response_card(user_id):
    response = '你有任何一家銀行的信用卡？'

    data['status'] = 3.2

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(
            text = response,
            quick_replies = [
                TextQuickReply(title = '有', payload = 'card_loan_yes'),
                TextQuickReply(title = '沒有', payload = 'card_loan_no')
            ]
        )
    )

def card_loan_response_owe_money(user_id):
    response = '你是否還有信用卡分期或循環未還？小提醒：要包含所有銀行唷！'

    data['status'] = 3.3

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(
            text = response,
            quick_replies = [
                TextQuickReply(title = '是', payload = 'card_loan_yes'),
                TextQuickReply(title = '否', payload = 'card_loan_no')
            ]
        )
    )

def loan_response_phone(user_id):
    if data['try'] == 0:
        response = '已把您的需求跟專員說了～\n幫我留下常用的聯絡電話，專員會再主動聯絡您～'
        if data['status'] != 2.5 and data['status'] != 3.4:
            data['status'] += 0.1
    else:
        response = '您的電話有錯誤，請再檢查一下'

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(text = response)
    )

def loan_response_end(user_id):
    response = '感謝你，專員將於一個工作天內與你聯繫～'

    data['status'] = 0

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C21]')

    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(text = response)
    )

# 其他
def retry_response(user_id):
    response = '你想要做什麼？'

    data['try'] = 0
    data['last_status'] = data['status']
    data['status'] = 0

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    buttons_template_message = TemplateSendMessage(
        template = ButtonsTemplate(
            text = response,
            buttons = [
                PostbackAction(
                    title = '我想問其他問題',
                    payload = 'other'
                ),
                PostbackAction(
                    title = '我要繼續回答',
                    payload = 'continue'
                )
            ] 
        )
    )
    
    fb_bot_api.push_message(
        user_id, 
        message = buttons_template_message
    )

def not_understand_response(user_id):
    response = '對不起～你的問題小i不是很清楚，可以換一個方式問，我會盡力回答您，謝謝～'

    save_data_assistant(user_id, response, '[C00]', '[C11]', '[C20]')
    
    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(text = response)
    )

def greeting_response(user_id):
    response = 'Hello～歡迎問小i各種關於外匯、信用卡，以及貸款的問題喔～'

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    generic_template_message = TemplateSendMessage(
        template = GenericTemplate(
            elements = [
                GenericElement(
                    title = '外匯',
                    subtitle = '可以查詢匯率與換算金額唷～',
                    buttons = [
                        PostbackAction(title = '我想要換外幣', payload = 'foreign_currency'),
                        PostbackAction(title = '現在匯率多少', payload = 'exchange_rate'),
                        URLAction(
                            title = '匯率官網',
                            url = 'https://www.esunbank.com.tw/bank/personal/deposit/rate/forex/foreign-exchange-rates',
                            webview_height_ratio = 'full',
                            messenger_extensions = None,
                            fallback_url = None
                        )
                    ]
                ),
                GenericElement(
                    title = '信用卡',
                    subtitle = '不知道要辦哪張卡嗎？',
                    buttons = [
                        PostbackAction(title = '哪張卡適合我', payload = 'credit_card'),
                        PostbackAction(title = '熱門卡片介紹', payload = 'hot_credit_card'),
                        URLAction(
                            title = '信用卡官網',
                            url = 'https://www.esunbank.com.tw/bank/personal/credit-card/intro',
                            webview_height_ratio = 'full',
                            messenger_extensions = None,
                            fallback_url = None
                        )
                    ]
                ),
                GenericElement(
                    title = '貸款',
                    subtitle = '回答一些問題，會派專員跟你聯繫～',
                    buttons = [
                        PostbackAction(title = '我有信貸需求', payload = 'card_loan'),
                        PostbackAction(title = '我有房貸需求', payload = 'house_loan'),
                        URLAction(
                            title = '房貸官網',
                            url = 'https://www.esunbank.com.tw/s/HouseLoan/Registration',
                            webview_height_ratio = 'full',
                            messenger_extensions = None,
                            fallback_url = None
                        )
                    ]
                )
            ]
        )
    )        
    
    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(text = response)
    )

    fb_bot_api.push_message(
        user_id, 
        message = generic_template_message
    ) 

def start_new_dialog_response(user_id):
    response = '你可以繼續問其他問題囉！如果不知道小i能做什麼，可以按下面的按鈕問我喔～'

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    buttons_template_message = TemplateSendMessage(
        template = ButtonsTemplate(
            text = response,
            buttons = [
                PostbackAction(
                    title = '小i能做什麼',
                    payload = 'greeting'
                )
            ] 
        )
    )
    
    fb_bot_api.push_message(
        user_id, 
        message = buttons_template_message
    )

def continue_dialog_response(user_id):
    if data['last_status'] == 8.2:
        foreign_currency_response_amount(user_id, data['foreign_currency'])

    elif data['last_status'] == 2.1:
        house_loan_response_amount(user_id)

    elif data['last_status'] == 2.4:
        house_loan_response_address(user_id)

    elif data['last_status'] == 2.5 or data['last_status'] == 3.4:
        data['status'] = data['last_status']
        loan_response_phone(user_id)

    elif data['last_status'] == 0:
        not_understand_response(user_id)
    
def other_response(user_id, text):
    response = generate_response(text)

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')
    
    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(text = response)
    )


@app.route('/')
def index():
    return '<p>Success</p>'

@app.route('/callback', methods = ['GET'])
def verify():
    
    if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.challenge'):
        
        if not request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return 'Verification token mismatch', 403
        return request.args['hub.challenge'], 200

    return 'Hello world', 200


@app.route('/callback', methods = ['POST'])
def webhook():

    # endpoint for processing incoming messaging events

    body = request.get_json()
    handler.handle(body)
    
    return 'ok', 200


@handler.add(GetStartedEvent)
def handle_get_started(event):
    
    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(text = 'Welcome to this page/app...')
    )    
    
    # set welcome message   


@handler.add(TextMessageEvent)
def handle_text_message(event):
    
    time = event.timestamp / 1000
    
    text = event.message.text
    print(text)
    
    user_id = event.sender.id
    
    save_data_user(user_id, text, time, '[U01]')

    print(data)

    # assistant 有問問題
    if data['status'] != 0:

        # 外幣
        if data['status'] == 8:
            currency = foreign_currency(text)
            if currency == None:
                # 看是不是銀行相關的其他服務
                pass
            else:
                currency = 'foreign_' + currency
                foreign_currency_response_transaction(user_id, currency)

        elif data['status'] == 8.1:
            transaction = foreign_currency_transaction(text)
            if transaction == None:
                # 看是不是銀行相關的其他服務
                pass
            else:
                transaction = data['foreign_currency'] + '_' + transaction
                foreign_currency_response_amount(user_id, transaction)

        elif data['status'] == 8.2:
            result = foreign_currency_amount(text)
            if len(result) != 2:
                data['try'] += 1
                if data['try'] > 1:
                    retry_response(user_id)
                else:
                    foreign_currency_response_amount(user_id, data['foreign_currency'])
            else:
                currency, transaction = data['foreign_currency'][8:11], data['foreign_currency'][12:]
                print(currency, transaction)
                if result[0] != 'TWD' and result[0] != currency:
                    data['try'] += 1
                    if data['try'] > 1:
                        retry_response(user_id)
                    else:
                        foreign_currency_response_amount(user_id, data['foreign_currency'])
                else:
                    foreign_currency_response_end(user_id, currency, transaction, result[0], result[1])

        # 匯率
        elif data['status'] == 6:
            way = exchange_rate_way(text)
            if way == None:
                data['status'] = 0
                # 看是不是銀行相關的其他服務
                pass
            elif way == 'all_exchange_rate':
                exchange_rate_response_all_currency(user_id)
            else:
                exchange_rate_response_currency(user_id)
        
        elif data['status'] == 6.1:
            currency = foreign_currency(text)
            if currency == None:
                # 看是不是銀行相關的其他服務
                pass
            else:
                exchange_rate_response_end(user_id, currency)

        # 房貸
        elif data['status'] == 2:
            data['try'] = 0
            house_loan_response_amount(user_id)
        
        elif data['status'] == 2.1:
            try:
                int(text)
                house_loan_response_purpose(user_id)
            except:
                data['try'] += 1
                if data['try'] > 1:
                    retry_response(user_id)
                else:
                    house_loan_response_amount(user_id)

        elif data['status'] == 2.2:
            house_loan_response_own(user_id)

        elif data['status'] == 2.3:
            data['try'] = 0
            house_loan_response_address(user_id)

        elif data['status'] == 2.4:
            if not house_loan_address(text):
                data['try'] += 1
                if data['try'] > 1:
                    retry_response(user_id)
                else:
                    house_loan_response_address(user_id)
            else:
                data['try'] = 0
                loan_response_phone(user_id)

        # 信貸
        elif data['status'] == 3:
            card_loan_response_salary(text)

        elif data['status'] == 3.1:
            card_loan_response_card(text)

        elif data['status'] == 3.2:
            card_loan_response_owe_money(text)

        elif data['status'] == 3.3:
            data['try'] = 0
            loan_response_phone(user_id)

        # 貸款總結
        elif data['status'] == 2.5 or data['status'] == 3.4:
            if re.match(r'09\d{8}', text) or re.match(r'09\d{2}-\d{3}-\d{3}', text):
                loan_response_end(user_id)
            else:
                data['try'] += 1
                if data['try'] > 1:
                    retry_response(user_id)
                else:
                    loan_response_phone(user_id)

    else:
        # 非相關，直接回不懂
        if not banking(text):
            not_understand_response(user_id)
        
        else:
            # 相關，看是哪個種類
            category = banking_category(text)
            
            # 外幣
            if category == 'ForeignCurrency':
                foreign_currency_response(user_id)

            # 匯率
            elif category == 'ExchangeRate':
                exchange_rate_response(user_id)

            # 信用卡
            elif category == 'CreditCard':
                credit_card_response(user_id)
            
            # 貸款
            elif category == 'Loan':
                loan_response(user_id)

            # 房貸
            elif category == 'HouseLoan':
                house_loan_response(user_id)

            # 信貸
            elif category == 'CardLoan':
                card_loan_response(user_id)

            # 打招呼
            elif category == 'Greeting':
                greeting_response(user_id)

            # 投資
            else:
                other_response(user_id, text)
        
  
@handler.add(QuickReplyMessageEvent) # quick reply action
def handle_quick_reply_message(event):

    time = event.timestamp / 1000

    text = event.message.text

    quick_reply_payload = event.message.quick_reply.payload
    
    user_id = event.sender.id

    save_data_user(user_id, text, time, '[U00]')

    # 外幣
    if quick_reply_payload.startswith('foreign_'):
        if data['status'] == 8:
            foreign_currency_response_transaction(user_id, quick_reply_payload)
            
        elif data['status'] == 8.1:
            data['try'] = 0
            foreign_currency_response_amount(user_id, quick_reply_payload)

    # 匯率
    elif quick_reply_payload.startswith('exchange_rate_'):
        exchange_rate_response_end(user_id, quick_reply_payload[14:])

    # 信用卡
    elif quick_reply_payload.startswith('credit_card_'):
        credit_card_response_end(user_id, text)

    # 房貸
    elif quick_reply_payload.startswith('house_loan_'):
        if data['status'] == 2:
            data['try'] = 0
            house_loan_response_amount(user_id)

        elif data['status'] == 2.2:
            house_loan_response_own(user_id)

        elif data['status'] == 2.3:
            data['try'] = 0
            house_loan_response_address(user_id)

    # 信貸
    elif quick_reply_payload.startswith('card_loan_'):
        if data['status'] == 3:
            card_loan_response_salary(user_id)

        elif data['status'] == 3.1:
            card_loan_response_card(user_id)

        elif data['status'] == 3.2:
            if quick_reply_payload[10:] == 'no':
                data['try'] = 0
                data['status'] = 3.3
                loan_response_phone(user_id)
            else:
                card_loan_response_owe_money(user_id)

        elif data['status'] == 3.3:
            data['try'] = 0
            loan_response_phone(user_id)

    else:
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(text='success qr')
        )


@handler.add(PostbackEvent) # button action
def handle_postback_message(event):

    text = event.postback.title

    button_payload = event.postback.payload
    
    user_id = event.sender.id

    time = event.timestamp / 1000

    save_data_user(user_id, text, time, '[U00]')
    
    if button_payload == 'greeting':
        greeting_response(user_id)

    elif button_payload == 'foreign_currency':
        foreign_currency_response(user_id)

    elif button_payload == 'exchange_rate':
        exchange_rate_response(user_id)

    elif button_payload == 'single_exchange_rate':
        exchange_rate_response_currency(user_id)

    elif button_payload == 'credit_card':
        credit_card_response(user_id)

    elif button_payload == 'hot_credit_card':
        credit_card_response_end(user_id, '熱門信用卡')

    elif button_payload == 'house_loan':
        house_loan_response(user_id)

    elif button_payload == 'card_loan':
        card_loan_response(user_id)

    elif button_payload == 'continue':
        continue_dialog_response(user_id)

    elif button_payload == 'other':
        start_new_dialog_response(user_id)

    else:
        fb_bot_api.push_message(
            user_id, 
            message = TextSendMessage(text = 'success btn')
        )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
