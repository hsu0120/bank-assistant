import os
import openai
from flask import Flask, request

import requests
from bs4 import BeautifulSoup

import re

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



app = Flask(__name__)

ACCESS_TOKEN = os.environ.get('PAGE_TOKEN')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
CHATGPT_TOKEN = os.environ.get('CHATGPT_TOKEN')

fb_bot_api = FacebookBotApi(ACCESS_TOKEN)

handler = WebhookHandler()

openai.api_key = CHATGPT_TOKEN

# file = openai.File.create(file=open('example.jsonl'), purpose='fine-tune')
# print(file)

# print(openai.File.list())
# files = openai.File.list()['data']
# print(files)
# file_id = files[0].id

# model_classification = openai.FineTune.create(training_file=file_id, model='davinci')
# print(model_classification)

# print(openai.FineTune.list())
models = openai.FineTune.list()['data']
fine_tuned_model = models[1].fine_tuned_model
print(fine_tuned_model)

def currency(dollar, en_dollar):
    r = requests.get('https://www.esunbank.com.tw/bank/personal/deposit/rate/forex/foreign-exchange-rates')
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'html.parser')
        
        dollar_info = soup.find_all('tr', {'class': en_dollar})[0]
        buy_instant = dollar_info.find_all('div', {'class': 'BBoardRate'})[0].string
        sell_instant = dollar_info.find_all('div', {'class': 'SBoardRate'})[0].string

        message = f'{dollar} \n\n我要賣{dollar} - 買匯價: {buy_instant} \n我要買{dollar} - 賣匯價: {sell_instant}'
        url = f'https://www.esunbank.com.tw/bank/personal/deposit/rate/forex/exchange-rate-chart#currency={en_dollar}'

    return message, url 

def currency_response(user_id):
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
                    payload='currency'
                )
            ] 
        )
    )
    
    fb_bot_api.push_message(
        user_id, 
        message=buttons_template_message
    )

def card_response(user_id):
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



# category = '6'

data = dict()

@app.route('/')
def index():
    return '<p>Success</p>'

@app.route('/callback', methods=['GET'])
def verify():
    
    if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.challenge'):
        
        if not request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return 'Verification token mismatch', 403
        return request.args['hub.challenge'], 200

    return 'Hello world', 200


@app.route('/callback', methods=['POST'])
def webhook():

    # endpoint for processing incoming messaging events

    body = request.get_json()
    handler.handle(body)
    
    return 'ok', 200


@handler.add(GetStartedEvent)
def handle_get_started(event):
    
    fb_bot_api.push_message(
        user_id, 
        message=TextSendMessage(text='Welcome to this page/app...')
    )    
    
    # set welcome message   

@handler.add(TextMessageEvent)
def handle_text_message(event):
    
    time = event.timestamp / 1000
    
    text = event.message.text
    print(text)
    
    user_id = event.sender.id
    
    if user_id not in data.keys():
        data[user_id] = dict()
        data[user_id]['conversation_log'] = list()
    
    data[user_id]['conversation_log'].append(text)
    data[user_id]['last_time'] = time
        
    print(data)

    category = openai.Completion.create(
        model=fine_tuned_model,
        prompt=f'Which category is this statement in: {text}',
        max_tokens=4,
        temperature=0
    )['choices'][0]['text']

    # if data[user_id]['status'] == 8.3:
    #     pass


    # 外幣
    if category.startswith('8'):
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(
                text = '你要換算哪個外幣呢？',
                quick_replies = [
                    TextQuickReply(title='美元 US', payload='foreign_US'),
                    TextQuickReply(title='人民幣 CN', payload='foreign_CN'),
                    TextQuickReply(title='港幣 HK', payload='foreign_HK'),
                    TextQuickReply(title='日圓 JP', payload='foreign_JP'),
                    TextQuickReply(title='歐元 EU', payload='foreign_EU')
                ]          
            )
        )
        data[user_id]['status'] = 8

    # 匯率
    elif category.startswith('6'):
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
                        payload='currency'
                    )
                ] 
            )
        )
        
        fb_bot_api.push_message(
            user_id, 
            message=buttons_template_message
        )

    # 信用卡
    elif category.startswith('13'):
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
    # 打招呼
    elif category.startswith('14'):

        generic_template_message = TemplateSendMessage(
            template=GenericTemplate(
                elements=[
                    GenericElement(
                        title='最新優惠',
                        buttons=[
                            URLAction(
                                title='本月精選外幣優惠',
                                url='https://www.esunbank.com.tw/bank/personal/deposit/deposit-event',
                                webview_height_ratio='full',
                                messenger_extensions=None,
                                fallback_url=None
                            ),
                            URLAction(
                                title='信用卡優惠',
                                url='https://www.esunbank.com.tw/bank/personal/credit-card/discount/shops#2',
                                webview_height_ratio='full',
                                messenger_extensions=None,
                                fallback_url=None
                            ),
                            URLAction(
                                title='開戶優惠',
                                url='https://event.esunbank.com.tw/mkt/OpenAccount/marketing/index.html',
                                webview_height_ratio='full',
                                messenger_extensions=None,
                                fallback_url=None
                            )
                        ]
                    ),
                    GenericElement(
                        title='外匯',
                        buttons=[
                            PostbackAction(title='服務總覽', payload='currency_info'),
                            PostbackAction(title='現在匯率多少', payload='currency_')
                        ]
                    ),
                    GenericElement(
                        title='房貸',
                        buttons=[
                            PostbackAction(title='服務總覽', payload='loan_info'),
                            URLAction(
                                title='額度利率評估',
                                url='https://www.esunbank.com.tw/s/HouseLoan/Registration',
                                webview_height_ratio='full',
                                messenger_extensions=None,
                                fallback_url=None
                            )
                        ]
                    ),
                    GenericElement(
                        title='信用卡',
                        buttons=[
                            PostbackAction(title='服務總覽', payload='card_info'),
                            PostbackAction(title='信用卡推薦', payload='card_')
                        ]
                    )
                ]
            )
        )        
        
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(text='Hello~歡迎問小i各種關於外匯、房貸，以及信用卡的問題喔~')
        )

        fb_bot_api.push_message(
            user_id, 
            message=generic_template_message
        ) 

    elif category.startswith('15'):
        response = openai.Completion.create(
            model='text-davinci-003',
            prompt=text,
            max_tokens=64,
            temperature=0.5,
        )

        # while (prediction >= 0.5):
        #     response = openai.Completion.create(
        #         model='text-davinci-003',
        #         prompt='「' + response + '」幫我換句話說',
        #         max_tokens=64,
        #         temperature=0.5,
        #     )
        
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(text=response['choices'][0]['text'])
        )

    # 房貸利率評估
    elif category.startswith('1'):
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
    
    else:
        response = openai.Completion.create(
            model='text-davinci-003',
            prompt=text,
            max_tokens=64,
            temperature=0.5,
        )

        # while (prediction >= 0.5):
        #     response = openai.Completion.create(
        #         model='text-davinci-003',
        #         prompt='「' + response + '」幫我換句話說',
        #         max_tokens=64,
        #         temperature=0.5,
        #     )
        
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(text=response['choices'][0]['text'])
        )

@handler.add(QuickReplyMessageEvent) # quick reply action
def handle_quick_reply_message(event):

    time = event.timestamp / 1000

    text = event.message.text

    quick_reply_payload = event.message.quick_reply.payload
    
    user_id = event.sender.id

    data[user_id]['text'].append(text)
    data[user_id]['time'].append(time)

    # 外幣
    if quick_reply_payload.startswith('foreign_'):
        data[user_id]['status'] += 0.1
        
        if data[user_id]['status'] == 8.1:
            payload_buy = quick_reply_payload + 'buy'
            payload_sell = quick_reply_payload + 'sell'

            fb_bot_api.push_message(
                user_id, 
                message=TextSendMessage(
                    text = '請問你是要?',
                    quick_replies = [
                        TextQuickReply(title='買現鈔', payload=payload_buy),
                        TextQuickReply(title='賣現鈔', payload=payload_sell)
                    ]          
                )
            )
            
        elif data[user_id]['status'] == 8.2:
            fb_bot_api.push_message(
                user_id, 
                message=TextSendMessage(text = '你要換多少呢?')
            )

    # 匯率
    elif quick_reply_payload.startswith('currency_'):
        if quick_reply_payload[9:] == 'US':
            send_message, send_url = currency('美元 US', 'USD')
        elif quick_reply_payload[9:] == 'CN':
            send_message, send_url = currency('人民幣 CN', 'CNY')
        elif quick_reply_payload[9:] == 'HK':
            send_message, send_url = currency('港幣 HK', 'HKD')
        elif quick_reply_payload[9:] == 'JP':
            send_message, send_url = currency('日圓 JP', 'JPY')
        elif quick_reply_payload[9:] == 'EU':
            send_message, send_url = currency('歐元 EU', 'EUR')

        buttons_template_message = TemplateSendMessage(
            template=ButtonsTemplate(
                text=send_message,
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
                        payload='currency'
                    )
                ]       
            )
        )
        
        fb_bot_api.push_message(
            user_id, 
            message=buttons_template_message
        )

    else:
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(text='success qr')
        )

@handler.add(PostbackEvent) # button action
def handle_postback_message(event):


    button_payload = event.postback.payload
    
    user_id = event.sender.id
    
    if button_payload == 'currency':
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(
                text = '你要查詢哪個外幣呢？',
                quick_replies = [
                    TextQuickReply(title='美元 US', payload='currency_US'),
                    TextQuickReply(title='人民幣 CN', payload='currency_CN'),
                    TextQuickReply(title='港幣 HK', payload='currency_HK'),
                    TextQuickReply(title='日圓 JP', payload='currency_JP'),
                    TextQuickReply(title='歐元 EU', payload='currency_EU')
                ]         
            )
        )

    elif button_payload == 'currency_':
        currency_response(user_id)

    elif button_payload == 'card_':
        card_response(user_id)

    else:
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(text='success btn')
        )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
