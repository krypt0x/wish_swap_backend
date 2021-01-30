import pika
import os
import traceback
import threading
import json
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wish_swap.settings')
import django
django.setup()

from wish_swap.settings import NETWORKS
from wish_swap.payments.api import parse_payment
from wish_swap.transfers.models import Transfer
from wish_swap.transfers.api import parse_execute_transfer_message


class Receiver(threading.Thread):
    def __init__(self, network):
        super().__init__()
        self.network = network

    def run(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            'rabbitmq',
            5672,
            os.getenv('RABBITMQ_DEFAULT_VHOST', 'wish_swap'),
            pika.PlainCredentials(os.getenv('RABBITMQ_DEFAULT_USER', 'wish_swap'), os.getenv('RABBITMQ_DEFAULT_PASS', 'wish_swap')),
        ))
        channel = connection.channel()
        channel.queue_declare(
                queue=self.network,
                durable=True,
                auto_delete=False,
                exclusive=False
        )
        channel.basic_consume(
            queue=self.network,
            on_message_callback=self.callback
        )
        print(f'RECEIVER: `{self.network}` queue was started', flush=True)
        channel.start_consuming()

    def payment(self, message):
        message['fromNetwork'] = self.network
        print('RECEIVER: payment message has been received', flush=True)
        parse_payment(message)

    def transfer(self, message):
        print('RECEIVER: transfer message has been received', flush=True)
        transfer = Transfer.objects.get(pk=message['transferId'])
        if message['success']:
            transfer = Transfer.objects.get(pk=message['transferId'])
            transfer.status = 'SUCCESS'
            print('RECEIVER: transfer confirmed successfully', flush=True)
        else:
            transfer.status = 'FAIL'
            print('RECEIVER: transfer was not completed, confirmation fail', flush=True)
        transfer.save()

    def execute_transfer(self, message):
        print('RECEIVER: execute transfer message has been received', flush=True)
        parse_execute_transfer_message(message, self.network)


    def callback(self, ch, method, properties, body):
        # print('RECEIVER: received', method, properties, body, flush=True)
        try:
            message = json.loads(body.decode())
            if message.get('status', '') == 'COMMITTED':
                getattr(self, properties.type, self.unknown_handler)(message)
        except Exception as e:
            print('\n'.join(traceback.format_exception(*sys.exc_info())),
                  flush=True)
        else:
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def unknown_handler(self, message):
        print('RECEIVER: Unknown message has been received', message, flush=True)


for network in NETWORKS.keys():
    receiver = Receiver(network)
    receiver.start()
    receiver = Receiver(network + '-transfers')
    receiver.start()
