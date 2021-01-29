import pika
import os
import json
from wish_swap.transfers.models import Transfer
from wish_swap.settings import NETWORKS
import time


def send_transfer_to_queue(transfer):
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        'rabbitmq',
        5672,
        os.getenv('RABBITMQ_DEFAULT_VHOST', 'wish_swap'),
        pika.PlainCredentials(os.getenv('RABBITMQ_DEFAULT_USER', 'wish_swap'),
                              os.getenv('RABBITMQ_DEFAULT_PASS', 'wish_swap')),
    ))
    channel = connection.channel()
    channel.queue_declare(
        queue=transfer.network + '-transfers',
        durable=True,
        auto_delete=False,
        exclusive=False
    )
    channel.basic_publish(
        exchange='',
        routing_key=transfer.network + '-transfers',
        body=json.dumps({'transferId': transfer.id}),
        properties=pika.BasicProperties(type='execute_transfer'),
    )
    connection.close()


def parse_execute_transfer_message(message):
    transfer = Transfer.objects.get(id=message['transferId'])
    if transfer.status not in ('WAITING FOR TRANSFER', 'HIGH GAS PRICE'):
        print(f'TRANSFER EXECUTING: there was already a transfer attempt', flush=True)
        return

    transfer.execute()
    transfer.save()

    if transfer.status == 'FAIL':
        print(f'TRANSFER EXECUTING: transfer failed with error {transfer.tx_error}', flush=True)
    else:
        decimals = (10 ** transfer.token.decimals)
        symbol = transfer.token.symbol
        print(f'TRANSFER EXECUTING: successful transfer {transfer.tx_hash} '
              f'{transfer.amount / decimals} {symbol} to {transfer.address}, '
              f'(fee) {transfer.fee_amount / decimals} {symbol} to {transfer.fee_address}', flush=True)

    timeout = NETWORKS[transfer.network]['transfer_timeout']
    print(f'TRANSFER EXECUTING: waiting {timeout} seconds before next transfer', flush=True)
    time.sleep(NETWORKS[transfer.network]['transfer_timeout'])