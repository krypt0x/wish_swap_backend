from rest_framework import serializers
from wish_swap.networks.models import GasInfo


class GasInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = GasInfo
        extra_kwargs = {
            'price': {'read_only': True},
            'status': {'read_only': True},
        }
        fields = (
            'network',
            'price',
            'price_limit',
            'status'
        )