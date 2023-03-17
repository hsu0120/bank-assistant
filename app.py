import os
import openai
from flask import Flask, request

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

# file = openai.File.create(file=open("example.jsonl"), purpose="fine-tune")
# print(file)

# print(openai.File.list())
# files = openai.File.list()['data']
# print(files)
# file_id = files[0].id

# model_classification = openai.FineTune.create(training_file=file_id, model="davinci")
# print(model_classification)

# print(openai.FineTune.list())
models = openai.FineTune.list()['data']
fine_tuned_model = models[0].fine_tuned_model
# print(fine_tuned_model)


answer = openai.Completion.create(
  model=fine_tuned_model,
  prompt="玩",
  max_tokens=32,
  temperature=0
)
print(answer['choices'][0]['text'])

data = dict()

@app.route('/')
def index():
    return "<p>Success</p>"

@app.route('/callback', methods=['GET'])
def verify():
    
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        
        if not request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200

    return "Hello world", 200


@app.route('/callback', methods=['POST'])
def webhook():

    # endpoint for processing incoming messaging events

    body = request.get_json()
    handler.handle(body)
    
    return "ok", 200


@handler.add(GetStartedEvent)
def handle_get_started(event):
    
    fb_bot_api.push_message(
        user_id, 
        message=TextSendMessage(text='Welcome to this page/app...')
    )    
    
    # set welcome message   

@handler.add(TextMessageEvent)
def handle_text_message(event):
    
    time = event.timestamp
    
    text = event.message.text
    print(text)
    
    user_id = event.sender.id
    
    if user_id not in data.keys():
        data[user_id] = dict()
        data[user_id]['text'] = list()
        data[user_id]['time'] = list()
    
    data[user_id]['text'].append(text)
    data[user_id]['time'].append(time)
        
    print(data)

    if text == "buttons":
        
        buttons_template_message = TemplateSendMessage(
            template=ButtonsTemplate(
                text="Buttons template",
                buttons=[
                    TextQuickReply(title="q1", payload="q1"),
                    PostbackAction(
                        title="postback",
                        payload="button_payload"
                    ),
                    URLAction(
                        title="url",
                        url="http://example.com/",
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
     
        
        
    elif text == "quick_reply":
        
        # Text Message quick reply
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(
                text = "Quick reply",
                quick_replies = [
                    TextQuickReply(title="q1", payload="q1"),
                    TextQuickReply(title="q2", payload="q2")
                ]          
            )
        )
        
        # Attachment Message quick reply
        
        # buttons_template = ButtonsTemplate(
        #     text="buttons_template",
        #     buttons= [
        #         PostbackAction(title="action_1", payload="payload_1"),
        #         PostbackAction(title="action_2", payload="payload_2")
        #     ])

        # templateSendMessage = TemplateSendMessage(
        #     template=buttons_template,
        #     quick_replies = [
        #         TextQuickReply(title="title1", payload="payload_1"),
        #         TextQuickReply(title="title2", payload="payload_2")
        #     ]
        # )       


#         fb_bot_api.push_message(
#             user_id, 
#             message=templateSendMessage
#         )              
        
    else:
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=text,
            max_tokens=64,
            temperature=0.5,
        )
        
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(text=response["choices"][0]["text"])
        )
    
@handler.add(QuickReplyMessageEvent) # quick reply action
def handle_quick_reply_message(event):
    payload = event.message.quick_reply.payload
    
    print(payload)
    
    user_id = event.sender.id
    
    fb_bot_api.push_message(
        user_id, 
        message=TextSendMessage(text="success qr")
    )

@handler.add(PostbackEvent) # button action
def handle_postback_message(event):

    postback_payload = event.postback.payload
    
    print(postback_payload)
    
    user_id = event.sender.id
    
    if postback_payload == "button_payload":
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(text="success button")
        )
    elif postback_payload == "reply_1":
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(text="success reply")
        )

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
