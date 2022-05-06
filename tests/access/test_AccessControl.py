import pytest
from pathlib import Path
from starkware.starknet.testing.starknet import Starknet
from utils import (
    Signer, TRUE, FALSE,
    assert_event_emitted, assert_revert,
    get_contract_def, cached_contract
)

DEFAULT_ADMIN_ROLE = 0
SOME_OTHER_ROLE = 42

signer = Signer(123456789987654321)


@pytest.fixture(scope='module')
def contract_defs():
    return {
        Path(key).stem: get_contract_def(key)
        for key in [
            'openzeppelin/account/Account.cairo',
            'tests/mocks/AccessControl.cairo',
        ]
    }


@pytest.fixture(scope='module')
async def accesscontrol_init(contract_defs):
    starknet = await Starknet.empty()
    account1 = await starknet.deploy(
        contract_def=contract_defs['Account'],
        constructor_calldata=[signer.public_key]
    )
    account2 = await starknet.deploy(
        contract_def=contract_defs['Account'],
        constructor_calldata=[signer.public_key]
    )
    accesscontrol = await starknet.deploy(
        contract_def=contract_defs['AccessControl'],
        constructor_calldata=[account1.contract_address]
    )
    return starknet.state, accesscontrol, account1, account2


@pytest.fixture
def accesscontrol_factory(contract_defs, accesscontrol_init):
    state, accesscontrol, account1, account2 = accesscontrol_init
    _state        = state.copy()
    accesscontrol = cached_contract(_state, contract_defs['AccessControl'], accesscontrol)
    account1      = cached_contract(_state, contract_defs['Account'], account1)
    account2      = cached_contract(_state, contract_defs['Account'], account2)
    return accesscontrol, account1, account2


@pytest.mark.asyncio
async def test_constructor(accesscontrol_factory):
    accesscontrol, account1, account2 = accesscontrol_factory

    expected1 = await accesscontrol.hasRole(DEFAULT_ADMIN_ROLE, account1.contract_address).call()
    assert expected1.result.hasRole == TRUE

    expected2 = await accesscontrol.hasRole(DEFAULT_ADMIN_ROLE, account2.contract_address).call()
    assert expected2.result.hasRole == FALSE

    expected3 = await accesscontrol.getRoleAdmin(DEFAULT_ADMIN_ROLE).call()
    assert expected3.result.admin == DEFAULT_ADMIN_ROLE


@pytest.mark.asyncio
async def test_grantRole(accesscontrol_factory):
    accesscontrol, account1, account2 = accesscontrol_factory

    tx_exec_info = await signer.send_transaction(account1, accesscontrol.contract_address, 'grantRole', [0, account2.contract_address])
    assert_event_emitted(
        tx_exec_info,
        from_address=accesscontrol.contract_address,
        name='RoleGranted',
        data=[
            DEFAULT_ADMIN_ROLE,        # role
            account2.contract_address, # account
            account1.contract_address  # sender
        ]
    )
    expected = await accesscontrol.hasRole(DEFAULT_ADMIN_ROLE, account2.contract_address).call()
    assert expected.result.hasRole == TRUE


@pytest.mark.asyncio
async def test_grantRole_unauthorized(accesscontrol_factory):
    accesscontrol, account1, account2 = accesscontrol_factory

    await assert_revert(
        signer.send_transaction(account2, accesscontrol.contract_address, 'grantRole', [DEFAULT_ADMIN_ROLE, account2.contract_address]),
        reverted_with="AccessControl: caller is missing role {}".format(DEFAULT_ADMIN_ROLE)
    )


@pytest.mark.asyncio
async def test_revokeRole(accesscontrol_factory):
    accesscontrol, account1, account2 = accesscontrol_factory

    await signer.send_transaction(account1, accesscontrol.contract_address, 'grantRole', [DEFAULT_ADMIN_ROLE, account2.contract_address])

    tx_exec_info = await signer.send_transaction(account2, accesscontrol.contract_address, 'revokeRole', [DEFAULT_ADMIN_ROLE, account1.contract_address])
    assert_event_emitted(
        tx_exec_info,
        from_address=accesscontrol.contract_address,
        name='RoleRevoked',
        data=[
            DEFAULT_ADMIN_ROLE,        # role
            account1.contract_address, # account
            account2.contract_address  # sender
        ]
    )
    expected = await accesscontrol.hasRole(DEFAULT_ADMIN_ROLE, account1.contract_address).call()
    assert expected.result.hasRole == FALSE


@pytest.mark.asyncio
async def test_revokeRole_unauthorized(accesscontrol_factory):
    accesscontrol, account1, account2 = accesscontrol_factory

    await assert_revert(
        signer.send_transaction(account2, accesscontrol.contract_address, 'revokeRole', [DEFAULT_ADMIN_ROLE, account1.contract_address]),
        reverted_with="AccessControl: caller is missing role {}".format(DEFAULT_ADMIN_ROLE)
    )


@pytest.mark.asyncio
async def test_renounceRole(accesscontrol_factory):
    accesscontrol, account1, account2 = accesscontrol_factory

    tx_exec_info = await signer.send_transaction(account1, accesscontrol.contract_address, 'renounceRole', [DEFAULT_ADMIN_ROLE, account1.contract_address])
    assert_event_emitted(
        tx_exec_info,
        from_address=accesscontrol.contract_address,
        name='RoleRevoked',
        data=[
            DEFAULT_ADMIN_ROLE,        # role
            account1.contract_address, # account
            account1.contract_address  # sender
        ]
    )
    expected = await accesscontrol.hasRole(DEFAULT_ADMIN_ROLE, account1.contract_address).call()
    assert expected.result.hasRole == FALSE


@pytest.mark.asyncio
async def test_renounceRole_unauthorized(accesscontrol_factory):
    accesscontrol, account1, account2 = accesscontrol_factory

    await assert_revert(
        signer.send_transaction(account1, accesscontrol.contract_address, 'renounceRole', [DEFAULT_ADMIN_ROLE, account2.contract_address]),
        reverted_with="AccessControl: can only renounce roles for self"
    )


@pytest.mark.asyncio
async def test_setRoleAdmin(accesscontrol_factory):
    accesscontrol, account1, account2 = accesscontrol_factory

    tx_exec_info = await signer.send_transaction(account1, accesscontrol.contract_address, 'setRoleAdmin', [DEFAULT_ADMIN_ROLE, SOME_OTHER_ROLE])
    assert_event_emitted(
        tx_exec_info,
        from_address=accesscontrol.contract_address,
        name='RoleAdminChanged',
        data=[
            DEFAULT_ADMIN_ROLE, # role
            DEFAULT_ADMIN_ROLE, # previousAdminRole
            SOME_OTHER_ROLE     # newAdminRole
        ]
    )
    expected = await accesscontrol.getRoleAdmin(DEFAULT_ADMIN_ROLE).call()
    assert expected.result.admin == SOME_OTHER_ROLE

    # test role admin cycle
    await signer.send_transaction(account1, accesscontrol.contract_address, 'grantRole',  [SOME_OTHER_ROLE, account2.contract_address])
    await signer.send_transaction(account2, accesscontrol.contract_address, 'revokeRole', [DEFAULT_ADMIN_ROLE, account1.contract_address])
