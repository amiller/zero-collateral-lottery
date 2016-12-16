from ethereum import tester, utils
import bitcoin
import os
import random

from ethereum import slogging
slogging.configure(':INFO')
#slogging.configure(':DEBUG,vm:TRACE')
import numpy as np

deposit_code = open("deposit.se").read()
weakcoin_code = open("twoplayer.se").read()

BLOCKS_PER_STEP = 6

tester.gas_limit = 1000000
zfill = lambda s: (32-len(s))*'\x00' + s

s = tester.state()

c1 = s.abi_contract(deposit_code)

class Player(object):
    def __init__(self, sk):
        self.sk = sk
        self.address = utils.privtoaddr(sk)

keys = [tester.k1,tester.k2,tester.k3,tester.k4,tester.k5,tester.k6,tester.k7,tester.k8]
addrs = map(utils.privtoaddr, keys)

players = [Player(sk) for i,sk in enumerate(keys)]

        
def build_tournament(N):
    assert np.log2(N) == int(np.log2(N))
    assert N >= 2

    # Create the deposit contract (but do not initialize yet)
    g = s.block.gas_used
    deposit = s.abi_contract(deposit_code)
    gas_deposit = s.block.gas_used - g # Store the gas_deposit to report later
    
    levels = int(np.log2(N))
    tournament = []
    tournament.append([])

    # Initilize Deadlines
    global TStart, TFinal
    TStart = 5   # Enough time for depositing
    TFinal = TStart + BLOCKS_PER_STEP * 3 * levels
    
    # Create the first level of contracts
    for i in range(N/2):
        tournament[0].append(s.abi_contract(weakcoin_code))
        T0 = TStart
        T1 = T0 + BLOCKS_PER_STEP
        T2 = T1 + BLOCKS_PER_STEP
        tournament[0][i].initFirstLevel(deposit.address, i, T0, T1, T2)

    # Connect each level to the previous level in order
    for level in range(1,levels):
        tournament.append([])
        T0 = TStart + (BLOCKS_PER_STEP * 2) * level
        T1 = T0 + BLOCKS_PER_STEP
        T2 = T1 + BLOCKS_PER_STEP        
        for i in range(2**(levels - level - 1)):
            print 'initlevel', level, i
            g = s.block.gas_used
            c = s.abi_contract(weakcoin_code)
            c.initLevel(tournament[level-1][2*i  ].address,
                        tournament[level-1][2*i+1].address,
                        T0, T1, T2
            )
            print 'initLevel:', s.block.gas_used - g
            print 'ok'
            tournament[level].append(c)

    # Hook the tournament up to the deposit contract
    g = s.block.gas_used
    deposit.initialize(N, TStart, TFinal, tournament[1][0].address)
    gas_deposit += s.block.gas_used - g # increment gas_deposit counter
    print 'deposit initialize', gas_deposit
    return tournament, deposit

# Create the tournament
global tournament, dep
tournament, dep = build_tournament(8)

# Each player takes a turn depositing
for p in players:
    g = s.block.gas_used
    dep.deposit(value=1, sender=p.sk)
    print 'DEPOSIT GAS', s.block.gas_used - g

# Advance past TStart
s.mine(8)

# Each player flips a coin
next_players = list(players) # create a new list filled with the players
for level in range(len(tournament)):
    for i,contract in enumerate(tournament[level]):
        left  = next_players[2*i+0]
        right = next_players[2*i+1]
        # Create secret for each player
        left. secret = os.urandom(32)
        right.secret = os.urandom(32)
        left. commit = utils.sha3(zfill(left.address) + left. secret)
        right.commit = utils.sha3(zfill(right.address) + right.secret)

        print level, i
        g = s.block.gas_used
        contract.commit(left. commit, sender= left.sk)
        print 'COMMIT GAS', s.block.gas_used - g
        contract.commit(right.commit, sender=right.sk)

    # Advance through the next step
    s.mine(BLOCKS_PER_STEP)

    # Open commitments for each player
    for i,contract in enumerate(tournament[level]):
        left  = next_players[2*i+0]
        right = next_players[2*i+1]

        print 'opening', level, i
        contract.open(left. secret, sender= left.sk)
        g = s.block.gas_used
        contract.open(right.secret, sender=right.sk)
        print 'OPEN GAS', s.block.gas_used - g

    # Advance through T2
    s.mine(BLOCKS_PER_STEP)
        
    # Check the winner commitments for each player
    next_players_new = []
    for i,contract in enumerate(tournament[level]):
        # Predict the local winner, assert it matches the contract value
        print 'i', contract.getWinner()
        if utils.int_to_addr(contract.getWinner()) == next_players[2*i].address:
            print 'Left won!'
            next_players_new.append(next_players[2*i+0])
        else:
            assert utils.int_to_addr(contract.getWinner()) == next_players[2*i+1].address
            print 'Right won!'
            next_players_new.append(next_players[2*i+1])

    next_players = next_players_new

# Advance through the next step
s.mine(6)
