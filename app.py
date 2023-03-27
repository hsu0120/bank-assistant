import os
import openai
import datetime
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

fb_bot_api = FacebookBotApi(ACCESS_TOKEN)

handler = WebhookHandler()

openai.api_key = CHATGPT_TOKEN

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

    return True if result == 'Banking' else False

def foreign_currency(text):
    result = openai.Completion.create(
        model = 'text-davinci-003',
        prompt = f'Does the following statement includes currency, if yes what is the currency abbreviation in three English letters, except TWD?\n\n{text}\nCurrency:',
        temperature = 0,
        max_tokens = 6,
        top_p = 1,
        frequency_penalty = 0,
        presence_penalty = 0
    )['choices'][0]['text'].replace(' ', '', 1)
    return result if result != 'No' else None

def foreign_currency_transaction(text):
    result = openai.Completion.create(
        model = 'text-davinci-003',
        prompt = f'The following is a statement and the category it falls into: buy_cash, sell_cash, buy_foreign_currency, sell_foreign_currency\n\n{text}\nCategory:',
        temperature = 0,
        max_tokens = 6,
        top_p = 1,
        frequency_penalty = 0,
        presence_penalty = 0
    )['choices'][0]['text'].replace(' ', '', 1)
    return result.lower() if result.startswith('None') else None

def foreign_currency_amount(text):
    result = openai.Completion.create(
        model = 'text-davinci-003',
        prompt = f'Does the following statement includes both currency and amount, if yes what is the currency abbreviation in three English letters and the amount? If no, which is missing?\n\n{text}\nCurrency/Amount:',
        temperature = 0,
        max_tokens = 6,
        top_p = 1,
        frequency_penalty = 0,
        presence_penalty = 0
    )['choices'][0]['text'].replace(' ', '', 1).replace(' ', '/')
    print(result)
    return result


# 處理資料
def save_data_user(user_id, text, time, u0):
    if (user_id not in data.keys()) or (int(time) - int(data[user_id]['last_time'])) > 1800:
        data[user_id] = dict()
        data[user_id]['status'] = 0
        data[user_id]['conversation_log'] = list()
        data[user_id]['bert_input'] = '[CLS]'

    data[user_id]['conversation_log'].append('{"role": "user", ' \
                                             f'"content": "{text}"' \
                                             '}')
    data[user_id]['bert_input'] += f'{u0}{text}^'
    data[user_id]['last_time'] = time

    print(data)

def save_data_assistant(user_id, response, c0, c1, c2):
    data[user_id]['conversation_log'].append('{"role": "assistant", ' \
                                             f'"content": "{response}"' \
                                             '}')
    data[user_id]['bert_input'] += f'{response}{c0}{c1}{c2}^'

    print(data)

# 匯率相關
def get_exchange_rate(currency, rate):
    r = requests.get('https://www.esunbank.com.tw/bank/personal/deposit/rate/forex/foreign-exchange-rates')
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'html.parser')
        
        dollar_info = soup.find_all('tr', {'class': currency})[0]
        exchange_rate = dollar_info.find_all('div', {'class': rate})[0].string

    return exchange_rate

def get_exchange_rate_response(dollar, en_dollar):
    r = requests.get('https://www.esunbank.com.tw/bank/personal/deposit/rate/forex/foreign-exchange-rates')
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'html.parser')
        
        dollar_info = soup.find_all('tr', {'class': en_dollar})[0]
        buy_instant = dollar_info.find_all('div', {'class': 'BBoardRate'})[0].string
        sell_instant = dollar_info.find_all('div', {'class': 'SBoardRate'})[0].string

        message = f'{dollar} \n\n我要賣{dollar} - 買匯價: {buy_instant} \n我要買{dollar} - 賣匯價: {sell_instant}'
        url = f'https://www.esunbank.com.tw/bank/personal/deposit/rate/forex/exchange-rate-chart#currency={en_dollar}'

    return message, url 

def exchange_rate_response(user_id):
    response = '請問你要查個別外幣匯率，還是要一次瀏覽多種外幣別呢？'

    save_data_assistant(user_id, response, '[C00]', '[C11]', '[C20]')

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
                    payload = 'exchange_rate'
                )
            ] 
        )
    )
    
    fb_bot_api.push_message(
        user_id, 
        message = buttons_template_message
    )

    data[user_id]['status'] = 0

# 外幣相關
def foreign_currency_response(user_id):
    response = '你要換算哪個外幣呢？'

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
    data[user_id]['status'] = 8

def foreign_currency_response_transaction(user_id, currency):
    response = '請問你是要?'

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    data[user_id]['status'] = 8.1
    data[user_id]['foreign_currency'] = currency

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
    currency = data[user_id]['foreign_currency'][8:11]
    response = f'你要換多少呢?(請記得輸入幣別喔)\nEx: {currency} 100 或 TWD 1000'

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    data[user_id]['status'] = 8.2
    data[user_id]['foreign_currency'] = transaction

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
        result = ex_amount * exchange_rate
    else:
        result = ex_amount * (1 / exchange_rate)
        currency = 'TWD'

    date = str(datetime.datetime.now()).split('.')[0]
    response = f'{ex_currency} {ex_amount} = {currency} {result}\n報價時間: {date}'

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C21]')

    generic_template_message = TemplateSendMessage(
        template=GenericTemplate(
            elements=[
                GenericElement(
                    title='貨幣換算結果',
                    subtitle='本匯率換算僅供參考，實際成交價依交易時間而定。',
                    buttons=[
                        PostbackAction(title='調整換算金額', payload='foreign_'),
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
def credict_card_response(user_id):
    response = '請問你喜歡以下哪一種類型的卡片呢? 我將根據你的偏好，立刻推薦適合的卡片'

    save_data_assistant(user_id, response, '[C00]', '[C10]', '[C20]')

    fb_bot_api.push_message(
        user_id, 
        message = TextSendMessage(
            text = response,
            quick_replies = [
                TextQuickReply(title = '網購族', payload = 'card_web'),
                TextQuickReply(title = '百貨購物族', payload = 'card_department'),
                TextQuickReply(title = '生活達人族', payload = 'card_life'),
                TextQuickReply(title = '出國旅遊族', payload = 'card_trip'),
                TextQuickReply(title = '聯名卡', payload = 'card_signed')
            ]          
        )
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

# 其他
def retry_response(user_id):
    response = '你想要做什麼？'

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

    data[user_id]['status'] = 0

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
                        PostbackAction(title = '我要換外幣', payload = 'foreign_currency'),
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
                        PostbackAction(title = '哪張卡適合我', payload = 'card_info'),
                        PostbackAction(title = '熱門卡片介紹', payload = 'card'),
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
                    subtitle = '回答一些問體，會派專員跟你聯繫～',
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

    # assistant 有問問題
    if data[user_id]['status'] != 0:

        # 外幣
        if data[user_id]['status'] == 8:
            currency = foreign_currency(text)
            if currency == None:
                # 看是不是銀行相關的其他服務
                pass

            currency = 'foreign_' + currency
            foreign_currency_response_transaction(user_id, currency)

        elif data[user_id]['status'] == 8.1:
            transaction = foreign_currency_transaction(text)
            if transaction == None:
                # 看是不是銀行相關的其他服務
                pass
            data[user_id]['try'] = 0
            transaction = data[user_id]['foreign_currency'] + '_' + transaction
            foreign_currency_response_amount(user_id, transaction)

        elif data[user_id]['status'] == 8.2:
            result = foreign_currency_amount(text)
            if (result.startswith('No')) or not (any(t.isdigit() for t in text)):
                data[user_id]['try'] += 1
                if data[user_id]['try'] > 1:
                    retry_response(user_id)
                else:
                    foreign_currency_response_amount(user_id, data[user_id]['foreign_currency'])
            else:
                result = result.replace(' ', '').split('/')
                ex_currency, ex_amount = result[0], result[1]
                currency, transaction = data[user_id]['foreign_currency'][8:11], data[user_id]['foreign_currency'][12:]
                
                if ex_currency != 'TWD' and ex_currency != currency:
                    data[user_id]['try'] += 1
                    if data[user_id]['try'] > 1:
                        retry_response(user_id)
                    else:
                        foreign_currency_response_amount(user_id, data[user_id]['foreign_currency'])
                else:
                    foreign_currency_response_end(user_id, currency, transaction, ex_currency, ex_amount)

    else:
        # 非相關，直接回不懂
        if not banking(text):
            not_understand_response(user_id)
        

        else:
            # 相關，看是哪個種類
            category = openai.Completion.create(
                            model = 'text-davinci-003',
                            prompt = 'The following is a statement and the category it falls into: ' \
                                     'greeting, credict card, foreign currency, exchange rate, loan, deposit, investment, branch' \
                                    f'\n\n{text}\nCategory: ',
                            temperature = 0,
                            max_tokens = 6,
                            top_p = 1,
                            frequency_penalty = 0,
                            presence_penalty = 0
                        )['choices'][0]['text'].replace(' ', '')
            
            # 外幣
            if category == 'ForeignCurrency':
                foreign_currency_response(user_id)

            # 匯率
            elif category == 'ExchangeRate':
                exchange_rate_response(user_id)

            # 信用卡
            elif category == 'CredictCard':
                credict_card_response(user_id)
            
            # 房貸利率評估
            elif category == 'Loan':
                loan_response(user_id)

            # 打招呼
            elif category == 'Greeting':
                greeting_response(user_id)

            # 投資
            elif category == 'Investment':
                investment_response(user_id)

            else:
                pass
        
  
@handler.add(QuickReplyMessageEvent) # quick reply action
def handle_quick_reply_message(event):

    time = event.timestamp / 1000

    text = event.message.text

    quick_reply_payload = event.message.quick_reply.payload
    
    user_id = event.sender.id

    save_data_user(user_id, text, time, '[U00]')

    # 外幣
    if quick_reply_payload.startswith('foreign_'):
        if data[user_id]['status'] == 8:
            foreign_currency_response_transaction(user_id, quick_reply_payload)
            
        elif data[user_id]['status'] == 8.1:
            data[user_id]['try'] = 0
            foreign_currency_response_amount(user_id, quick_reply_payload)


    # 匯率
    elif quick_reply_payload.startswith('currency_'):
        if quick_reply_payload[9:] == 'USD':
            response, send_url = get_exchange_rate_response('美元 USD', 'USD')
        elif quick_reply_payload[9:] == 'CNY':
            response, send_url = get_exchange_rate_response('人民幣 CNY', 'CNY')
        elif quick_reply_payload[9:] == 'HKD':
            response, send_url = get_exchange_rate_response('港幣 HKD', 'HKD')
        elif quick_reply_payload[9:] == 'JPY':
            response, send_url = get_exchange_rate_response('日圓 JPY', 'JPY')
        elif quick_reply_payload[9:] == 'EUR':
            response, send_url = get_exchange_rate_response('歐元 EUR', 'EUR')

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

    elif quick_reply_payload == 'exchange_rate':
        buttons_template_message = TemplateSendMessage(
            template=ButtonsTemplate(
                text='請問你要查個別外幣匯率，還是要一次瀏覽多種外幣別呢？',
                buttons=[
                    URLAction(
                        title='查看所有幣別匯率',
                        url='https://www.esunbank.com.tw/bank/personal/deposit/rate/forex/foreign-exchange-rates',
                        webview_height_ratio='full',
                        messenger_extensions=None,
                        fallback_url=None
                    ),
                    PostbackAction(
                        title='個別外幣匯率',
                        payload='exchange_rate'
                    )
                ] 
            )
        )
        
        fb_bot_api.push_message(
            user_id, 
            message=buttons_template_message
        )

    elif quick_reply_payload == 'card':
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(
                text = '請問你喜歡以下哪一種類型的卡片呢?\n我將根據你的偏好，立刻推薦適合的卡片',
                quick_replies = [
                    TextQuickReply(title='網購族', payload='card_web'),
                    TextQuickReply(title='百貨購物族', payload='card_department'),
                    TextQuickReply(title='生活達人族', payload='card_life'),
                    TextQuickReply(title='出國旅遊族', payload='card_trip'),
                    TextQuickReply(title='聯名卡', payload='card_signed')
                ]          
            )
        )

    elif quick_reply_payload == 'loan':
        buttons_template_message = TemplateSendMessage(
            template=ButtonsTemplate(
                text='透過簡單15題以內的問卷，只要「3分鐘」就可以「線上」、「免費」獲得「專屬」的可貸款額度，還有專屬優惠利率，線上立即申請，享有優惠三選一方案',
                buttons=[
                    URLAction(
                        title='額度利率評估',
                        url='https://www.esunbank.com.tw/s/HouseLoan/Registration',
                        webview_height_ratio='full',
                        messenger_extensions=None,
                        fallback_url=None
                    )
                ] 
            )
        )
        
        fb_bot_api.push_message(
            user_id, 
            message=buttons_template_message
        )
    elif quick_reply_payload == 'loan_suggestion':
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(text='建議你用以下六個技巧來挑選房貸喔！\n 1. 貸款成本：4種精算利率的方法（兩段式利率、固定或機動利率、銀行的附加費用、違約金的收取）\n2. 產品多樣化：選擇能提供多樣產品的銀行\n3. 附加價值：滿足一次購足的要求\n4. 服務品質：要從小處觀察\n5. 房貸專員：專業、熱忱、效率都重要\n6. 品牌價值：優先選口碑好的銀行')
        )

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
    
    if button_payload == 'exchange_rate':
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(
                text = '你要查詢哪個外幣呢？',
                quick_replies = [
                    TextQuickReply(title='美元 US', payload='exchange_rate_US'),
                    TextQuickReply(title='人民幣 CN', payload='exchange_rate_CN'),
                    TextQuickReply(title='港幣 HK', payload='exchange_rate_HK'),
                    TextQuickReply(title='日圓 JP', payload='exchange_rate_JP'),
                    TextQuickReply(title='歐元 EU', payload='exchange_rate_EU')
                ]         
            )
        )

    elif button_payload == 'exchange_rate_':
        currency_response(user_id)

    elif button_payload == 'exchange_rate_info':
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(
                text = '外匯相關問題',
                quick_replies = [
                    TextQuickReply(title='現在匯率多少', payload='exchange_rate'),
                    TextQuickReply(title='能換多少外幣', payload='foreign')
                ]         
            )
        )

    elif button_payload == 'card_':
        card_response(user_id)

    elif button_payload == 'card_info':
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(
                text = '信用卡相關問題',
                quick_replies = [
                    TextQuickReply(title='信用卡推薦', payload='card'),
                    TextQuickReply(title='辦卡相關', payload='create')
                ]         
            )
        )

    elif button_payload == 'loan_info':
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(
                text = '房貸相關問題',
                quick_replies = [
                    TextQuickReply(title='我能貸多少', payload='loan'),
                    TextQuickReply(title='該選哪個房貸', payload='loan_suggestion')
                ]         
            )
        )

    else:
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(text='success btn')
        )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
