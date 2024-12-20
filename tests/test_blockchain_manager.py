import unittest.mock
from typing import Optional

import pytest

from bt_ddos_shield.address import DefaultAddressSerializer
from bt_ddos_shield.blockchain_manager import (
    AbstractBlockchainManager,
    BittensorBlockchainManager,
)
from bt_ddos_shield.utils import Hotkey


class MemoryBlockchainManager(AbstractBlockchainManager):
    known_data: dict[Hotkey, bytes]
    put_counter: int

    def __init__(self):
        super().__init__(DefaultAddressSerializer())
        self.known_data = {}
        self.put_counter = 0

    def put(self, hotkey: Hotkey, data: bytes):
        self.known_data[hotkey] = data
        self.put_counter += 1

    def get(self, hotkey: Hotkey) -> Optional[bytes]:
        return self.known_data.get(hotkey)


class TestBittensorBlockchainManager:
    """
    Test suite for the blockchain manager.
    """

    def test_get(self):
        hotkey = "5EU2xVWC7qffsUNGtvakp5WCj7WGJMPkwG1dsm3qnU2Kqvee"

        mock_subtensor = unittest.mock.MagicMock()
        mock_substrate = mock_subtensor.substrate.__enter__.return_value
        mock_substrate.query.return_value = unittest.mock.Mock(
            value={
                "info": {
                    "fields": None,
                },
            },
        )

        manager = BittensorBlockchainManager(
            address_serializer=DefaultAddressSerializer(),
            subtensor=mock_subtensor,
            wallet=unittest.mock.Mock(),
            netuid=1,
        )

        assert manager.get(hotkey) is None

        mock_substrate.query.assert_called_once_with(
            module="Commitments",
            storage_function="CommitmentOf",
            params=[1, "5EU2xVWC7qffsUNGtvakp5WCj7WGJMPkwG1dsm3qnU2Kqvee"],
            block_hash=None,
        )

        mock_substrate.query.reset_mock()
        mock_substrate.query.return_value = unittest.mock.Mock(
            value={
                "info": {
                    "fields": [
                        {
                            "Raw4": "0x64617461",
                        },
                    ],
                },
            },
        )

        assert manager.get(hotkey) == b"data"

    def test_put(self):
        hotkey = "5EU2xVWC7qffsUNGtvakp5WCj7WGJMPkwG1dsm3qnU2Kqvee"

        mock_subtensor = unittest.mock.MagicMock()
        mock_substrate = mock_subtensor.substrate.__enter__.return_value

        mock_wallet = unittest.mock.Mock()
        mock_wallet.hotkey.ss58_address = hotkey

        manager = BittensorBlockchainManager(
            address_serializer=DefaultAddressSerializer(),
            subtensor=mock_subtensor,
            wallet=mock_wallet,
            netuid=1,
        )

        manager.put(hotkey, b"data")

        mock_substrate.compose_call.assert_called_once_with(
            call_module="Commitments",
            call_function="set_commitment",
            call_params={
                "netuid": 1,
                "info": {
                    "fields": [
                        [
                            {
                                "Raw4": b"data",
                            },
                        ],
                    ],
                },
            },
        )
        mock_substrate.create_signed_extrinsic.assert_called_once_with(
            call=mock_substrate.compose_call.return_value,
            keypair=mock_wallet.hotkey,
        )
        mock_subtensor.substrate.submit_extrinsic.assert_called_once_with(
            mock_substrate.create_signed_extrinsic.return_value,
            wait_for_inclusion=False,
            wait_for_finalization=True,
        )

    def test_put_not_own_hotkey(self):
        mock_wallet = unittest.mock.Mock()
        mock_wallet.hotkey.ss58_address = "MyHotkey"

        manager = BittensorBlockchainManager(
            address_serializer=DefaultAddressSerializer(),
            subtensor=unittest.mock.MagicMock(),
            wallet=mock_wallet,
            netuid=1,
        )

        with pytest.raises(ValueError):
            manager.put("SomeoneHotkey", b"data")
