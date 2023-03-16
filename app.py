import os
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

fb_bot_api = FacebookBotApi(ACCESS_TOKEN)

handler = WebhookHandler()

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
        
    text = event.message.text
    print(text)
    
    user_id = event.sender.id

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
    elif text == "generic":
        
        generic_template_message = TemplateSendMessage(
            template=GenericTemplate(
                elements=[
                    GenericElement(
                        title="GenericElement 1",
                        image_url="https://example.com/item1.jpg",
                        subtitle="description1",
                        default_action=URLAction(url="http://example.com/"),
                        buttons=[
                            PostbackAction(title="postback_1", payload="data_1"),
                            URLAction(
                                title="url_1",
                                url="http://example.com/1",
                                webview_height_ratio='full',
                                messenger_extensions=None,
                                fallback_url=None
                            )
                        ]
                    ),
                    GenericElement(
                        title="GenericElement 2",
                        image_url="https://example.com/item2.jpg",
                        subtitle="description2",
                        default_action=URLAction(url="http://example.com/"),
                        buttons=[
                            PostbackAction(title="postback_2", payload="data_2"),
                            URLAction(
                                title="url_2",
                                url="http://example.com/2",
                                webview_height_ratio='compact',
                                messenger_extensions=None,
                                fallback_url=None
                            )
                        ]
                    )
                ]
            )
        )        
        
        fb_bot_api.push_message(
            user_id, 
            message=generic_template_message
        )        
        
    elif text == "media":
        
        # by URL
        image_send_message = ImageSendMessage(url="https://via.placeholder.com/1024x1024")

        attachment_id = fb_bot_api.upload_attachment(image_send_message)        
        
        media_template_message = TemplateSendMessage(
            template=MediaTemplate(
                elements=[
                    ImageElement(
                        attachment_id=attachment_id,
                        buttons=[
                            PostbackAction(title="postback_1", payload="data_1"),
                        ]
                    )
                ]
            )
        )
        
        fb_bot_api.push_message(
            user_id, 
            message=media_template_message
        )           
        
        # by facebook
        
#         media_template_message = TemplateSendMessage(
#             template=MediaTemplate(
#                 elements=[
#                     VideoElement(
#                         # see documents: 
#                         # https://developers.facebook.com/docs/messenger-platform/send-messages/template/media#facebook_url
#                         facebook_url="https://www.facebook.com/{USER_NAME}/videos/<NUMERIC_ID>/",
#                         buttons=[
#                             PostbackAction(title="postback_1", payload="data_1"),
#                             URLAction(
#                                 title="url_1",
#                                 url="http://example.com/1",
#                                 webview_height_ratio='full',
#                                 messenger_extensions=None,
#                                 fallback_url=None
#                             )
#                         ]
#                     )
#                 ]
#             )
#         )
        
#         fb_bot_api.push_message(
#             user_id, 
#             message=media_template_message
#         )          
        
                
        
        
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
        
        
    elif text.lower() == "broadcast":
        
        text_message = TextMessage(text = "broadcast 1")
        
        fb_bot_api.broadcast(message = text_message)
        
    else:
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(text=text)
        )
    
@handler.add(QuickReplyMessageEvent)
def handle_quick_reply_message(event):
    payload = event.message.quick_reply.payload
    print(payload)
    user_id = event.sender.id
    
    fb_bot_api.push_message(
        user_id, 
        message=TextSendMessage(text="success qr")
    )

    
@handler.add(AttachmentMessageEvent, message=(ImageMessage, VideoMessage, AudioMessage))
def handle_content_message(event):
    
    url = event.message.attachment.payload.url
    
    user_id = event.sender.id
    
    if isinstance(event.message.attachment, ImageMessage):
        pass
        fb_bot_api.push_message(
            user_id, 
            message=ImageSendMessage(
                url = url
            )
        )
        
    elif isinstance(event.message.attachment, VideoMessage):
        
        fb_bot_apipush_message(
            user_id, 
            message=VideoSendMessage(
                url = url
            )
        )        
        
    elif isinstance(event.message.attachment, AudioMessage):
        
        fb_bot_apipush_message(
            user_id, 
            message=AudioSendMessage(
                url = url
            )
        )        
        
    else:
        return    
    
    
@handler.add(AttachmentMessageEvent, message=FileMessage)
def handle_file_message(event):
    
    print(event.message.attachment.type)
    
@handler.add(AttachmentMessageEvent, message=LocationMessage)
def handle_location_message(event):    

    print(event.message.attachment.type)
    
@handler.add(AttachmentMessageEvent, message=FallbackMessage)
def handle_fallback_message(event):    

    print(event.message.attachment.type)


@handler.add(PostbackEvent)
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

@handler.add(LinkingEvent)
def handle_linking(event):
    print("event.LinkingEvent")
    
@handler.add(UnLinkingEvent)
def handle_unlinking(event):
    print("event.UnLinkingEvent")    

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
