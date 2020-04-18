"""
BitShares Shorting Attacks Avenger

ensures you always have adequate collateral backing each debt
it also ensures you do not have too much collateral backing your debt
in either case, when out of bounds
it returns your collateral to the middle of the band specified

"""

# STANDARD PYTHON MODULES
from json import dumps as json_dumps
from json import loads as json_loads
from random import shuffle
from getpass import getpass
from pprint import pprint
import traceback
import time

# THIRD PARTY MODULES
from websocket import create_connection as wss

# SHORTING ATTACK AVERNGER MODULES
from dex_manual_signing import broker
from bitshares_nodes import bitshares_nodes


def logo():
    """

    ██████  ██ ████████ ███████ ██   ██  █████  ██████  ███████ ███████
    ██   ██ ██    ██    ██      ██   ██ ██   ██ ██   ██ ██      ██
    ██████  ██    ██    ███████ ███████ ███████ ██████  █████   ███████
    ██   ██ ██    ██         ██ ██   ██ ██   ██ ██   ██ ██           ██
    ██████  ██    ██    ███████ ██   ██ ██   ██ ██   ██ ███████ ███████

    ███████ ██   ██  ██████  ██████  ████████ ██ ███    ██  ██████
    ██      ██   ██ ██    ██ ██   ██    ██    ██ ████   ██ ██
    ███████ ███████ ██    ██ ██████     ██    ██ ██ ██  ██ ██   ███
         ██ ██   ██ ██    ██ ██   ██    ██    ██ ██  ██ ██ ██    ██
    ███████ ██   ██  ██████  ██   ██    ██    ██ ██   ████  ██████

     █████  ████████ ████████  █████   ██████ ██   ██
    ██   ██    ██       ██    ██   ██ ██      ██  ██
    ███████    ██       ██    ███████ ██      █████
    ██   ██    ██       ██    ██   ██ ██      ██  ██
    ██   ██    ██       ██    ██   ██  ██████ ██   ██

     █████  ██    ██ ███████ ███    ██  ██████  ███████ ██████
    ██   ██ ██    ██ ██      ████   ██ ██       ██      ██   ██
    ███████ ██    ██ █████   ██ ██  ██ ██   ███ █████   ██████
    ██   ██  ██  ██  ██      ██  ██ ██ ██    ██ ██      ██   ██
    ██   ██   ████   ███████ ██   ████  ██████  ███████ ██   ██

    """
    return it("green", logo.__doc__)

def sigfig(price):
    """
    format price to max 8 significant figures, return as float
    """
    return float("{:g}".format(float("{:.8g}".format(price))))

    
def it(style, text):
    """
    Color printing in terminal
    """
    emphasis = {
        "red": 91,
        "green": 92,
        "yellow": 93,
        "blue": 94,
        "purple": 95,
        "cyan": 96,
    }
    return ("\033[%sm" % emphasis[style]) + str(text) + "\033[0m"
    

def wss_handshake():
    """
    Create a websocket handshake
    """
    while True:
        nodes = bitshares_nodes()
        shuffle(nodes)
        node = nodes[0]
        start = time.time()
        rpc = wss(node, timeout=3)
        if time.time() - start < 3:
            break
    return rpc


def wss_query(rpc, params):
    """
    Send and receive websocket requests
    """
    query = json_dumps({"method": "call", "params": params, "jsonrpc": "2.0", "id": 1})
    print(query)
    rpc.send(query)
    ret = json_loads(rpc.recv())
    try:
        return ret["result"]  # if there is result key take it
    except Exception:
        print(ret)


def get_margin_positions(rpc, account_id_or_name):
    """
    Given asset names return asset ids and precisions
    """
    ret = wss_query(rpc, ["database", "get_margin_positions", [account_id_or_name]])
    return ret


def rpc_lookup_accounts(rpc, cache):
    """
    Given account name return A.B.C account id
    """
    ret = wss_query(rpc, ["database", "lookup_accounts", [cache["account_name"], 1]])
    return ret[0][1]


def rpc_last(rpc, pair):
    """
    Get the latest ticker price
    """
    ticker = wss_query(
        rpc, ["database", "get_ticker", [pair["currency"], pair["asset"], False]]
    )
    last = float(ticker["latest"])
    bid = float(ticker["highest_bid"])
    ask = float(ticker["lowest_ask"])
    if float(last) == 0:
        raise ValueError("zero price last")
    return last, bid, ask


def rpc_lookup_asset_symbols(rpc, assets):
    """
    Given asset names return asset ids and precisions
    """
    ret = wss_query(rpc, ["database", "lookup_asset_symbols", [assets]])
    ret = [i for i in ret if i is not None]
    return ret


def rpc_get_objects(rpc, object_id):
    """
    Return data about objects in 1.7.x, 2.4.x, 1.3.x, etc. format
    """
    ret = wss_query(rpc, ["database", "get_objects", [object_id,]])
    return ret


def personal_collateral_ratio(rpc, positions):
    """
    # 1 call for asset name and precision
    # use precision derived from call_price[base] and call_price[quote] asset_id's
    # rearrange collateral and debt, eliminate call price and borrower
        # collateral {human_amount, asset_id, asset_name}
        # debt {human_amount, asset_id, asset_name}
    # calculate collateral_ratio from "collateral" "debt", add key to positions
    """
    # Gather a list of asset id's from the positions lists
    assets = []
    for position in positions:
        assets.append(position["call_price"]["base"]["asset_id"])
        assets.append(position["call_price"]["quote"]["asset_id"])
    assets = list(set(assets))
    ret = rpc_get_objects(rpc, assets)
    detail = {}
    for item in ret:
        detail[item["id"]] = {
            "symbol": item["symbol"],
            "precision": item["precision"],
        }
        try:
            detail[item["id"]]["bitasset_data_id"] = item["bitasset_data_id"]
        except Exception:
            pass

    positions2 = []
    for _, position in enumerate(positions):
        # localize asset id
        collateral_id = position["call_price"]["base"]["asset_id"]
        debt_id = position["call_price"]["quote"]["asset_id"]
        # convert graphene amount to human amount
        collateral_amount = position["collateral"]
        debt_amount = position["debt"]
        collateral_precision = detail[collateral_id]["precision"]
        debt_precision = detail[debt_id]["precision"]
        collateral_amount /= 10 ** collateral_precision
        debt_amount /= 10 ** debt_precision
        # reformat the positions dictionary
        positions2.append(
            {
                "id": position["id"],
                "collateral": {
                    "id": collateral_id,
                    "symbol": detail[collateral_id]["symbol"],
                    "amount": sigfig(collateral_amount),
                    "precision": collateral_precision,
                },
                "debt": {
                    "id": debt_id,
                    "symbol": detail[debt_id]["symbol"],
                    "amount": sigfig(debt_amount),
                    "precision": debt_precision,
                    "bitasset_data_id": detail[debt_id]["bitasset_data_id"],
                },
            }
        )
    return positions2


def get_market_feed(rpc, positions):
    """
    # 2 get last bid ask price for each market via api call
    # add each to the positions dictionary
    """
    pair = {}
    for idx, position in enumerate(positions):
        positions[idx]["price"] = {}
    for idx, position in enumerate(positions):
        pair["asset"] = position["collateral"]["symbol"]
        pair["currency"] = position["debt"]["symbol"]
        last, bid, ask = rpc_last(rpc, pair)
        positions[idx]["price"]["last"] = sigfig(last)
        positions[idx]["price"]["bid"] = sigfig(bid)
        positions[idx]["price"]["ask"] = sigfig(ask)
    return positions


def get_settlement_feed(rpc, positions):
    """
    # 2 get the published feed price for each market via api call
    # add to the positions dictionary
    """
    for idx, position in enumerate(positions):
        bitasset_data = rpc_get_objects(rpc, [position["debt"]["bitasset_data_id"]])
        mcr = bitasset_data[0]["current_feed"]["maintenance_collateral_ratio"] / 1000
        graphene_settlement = bitasset_data[0]["current_feed"]["settlement_price"]
        human_base = (
            int(graphene_settlement["base"]["amount"])
            / 10 ** position["debt"]["precision"]
        )
        human_quote = (
            int(graphene_settlement["quote"]["amount"])
            / 10 ** position["collateral"]["precision"]
        )
        human_settlement = sigfig(human_base / human_quote)
        positions[idx]["price"]["settlement"] = human_settlement
        positions[idx]["collateral"]["maintenance_ratio"] = mcr
        min_price = min(position["price"]["last"], human_settlement)

        debt = positions[idx]["debt"]["amount"]

        collateral_ratio = min_price * position["collateral"]["amount"] / debt
        positions[idx]["collateral"]["current_ratio"] = sigfig(collateral_ratio)

        one_to_one = debt / human_settlement
        maintenance_price = mcr * one_to_one
        positions[idx]["collateral"]["one_to_one"] = sigfig(one_to_one)
        positions[idx]["collateral"]["maintenance"] = sigfig(maintenance_price)
        positions[idx]["collateral"]["mcr"] = mcr

    return positions


def input_buffer():
    """
    allow user input for refresh frequency and upper/lower limit on buffer percent
    """

    # default user input buffer values, 30 means 30% more than MCR
    buffer_min = 30
    buffer_max = 60
    # default user input refresh of positions
    buffer_minutes = 10

    try:
        print(
            f"""
        Input an integer Minimum Percent Buffer you would like to maintain over MCR
        or press Enter for Default buffer_min = {buffer_min}
            """
        )
        buffer_min = int(input("\nEnter a minimum percent buffer over MCR\n\n"))
    except Exception:
        print(buffer_min)

    try:
        print(
            f"""
        Input an integer Maximum Percent Buffer you would like to maintain over MCR
        or press Enter for Default buffer_max = {buffer_max}\n
        The Maximum Percent Buffer must be greater than the Minimum you just entered.
            """
        )
        buffer_max = int(input("\nEnter a maximum percent buffer over MCR\n\n"))
    except Exception:
        print(buffer_max)
    try:
        print(
            f"""
        Input an integer number of minutes you would like to wait
        between refreshing your collateral buffer?
        or press Enter for Default buffer_minutes = {buffer_minutes}
            """
        )
        buffer_minutes = int(
            input("\nEnter the buffer maintenance interval in minutes\n\n")
        )
    except Exception:
        print(buffer_minutes)

    if buffer_max < buffer_min:
        raise ValueError("buffer_max < buffer_min")
    if (buffer_max < 0) or (buffer_min < 0):
        raise ValueError("buffer must be greater than 0")
    if buffer_minutes < 0:
        raise ValueError("buffer pause minutes must be greater than 0")
    if buffer_minutes > 1440:
        raise ValueError("buffer pause minutes must be less than 1440")

    call_buffer = {
        "buffer_min": sigfig(buffer_min),
        "buffer_max": sigfig(buffer_max),
        "buffer_mid": sigfig((buffer_min + buffer_max) / 2),
        "buffer_minutes": buffer_minutes,
        "buffer_seconds": buffer_minutes * 60,
    }

    return call_buffer


def user_login():
    """
    Enter user name and wif
    """
    print("\033c")
    print(logo())
    name = input("Enter BitShares Account Name\n\n")
    wif = getpass("\nEnter BitShares Account WIF or press enter to skip\n\n")

    auth = {"account_name": name, "wif": wif}
    call_buffer = input_buffer()

    print("\n\n", auth["account_name"], "\n")
    pprint(call_buffer)
    user_resp = input("\n\nConfirm Y/N\n\n").lower()
    if user_resp == "n":
        user_login()

    return auth, call_buffer


def authenticate(auth):
    """
    Test if Account Name matches WIF
    """

    order = {
        "edicts": [{"op": "login"}],
        "header": {
            "asset_id": "1.3.0",
            "currency_id": "1.3.1",
            "asset_precision": 5,
            "currency_precision": 5,
            "account_id": auth["account_id"],
            "account_name": auth["account_name"],
            "wif": auth["wif"],
        },
        "nodes": bitshares_nodes(),
    }

    broker(order)
    print("\nAuthenticated\n")
    return True


def check_buffer(call_buffer, positions):
    """
    call_buffer = {
        "buffer_min": buffer_min,
        "buffer_max": buffer_max,
    }
    """
    for idx, position in enumerate(positions):
        positions[idx]["collateral"]["buffer_min"] = sigfig(
            position["collateral"]["maintenance"]
            * (1 + call_buffer["buffer_min"] / 100)
        )
        positions[idx]["collateral"]["buffer_max"] = sigfig(
            position["collateral"]["maintenance"]
            * (1 + call_buffer["buffer_max"] / 100)
        )
        positions[idx]["collateral"]["buffer_mid"] = sigfig(
            position["collateral"]["maintenance"]
            * (1 + call_buffer["buffer_mid"] / 100)
        )

    for idx, position in enumerate(positions):
        # localize min, mid, max buffer, and current collateral amount
        buffer_min = position["collateral"]["buffer_min"]
        buffer_mid = position["collateral"]["buffer_mid"]
        buffer_max = position["collateral"]["buffer_max"]
        amount = position["collateral"]["amount"]
        # calculate delta from mid, this is what we will give to update_call()
        positions[idx]["collateral"]["delta"] = sigfig(buffer_mid - amount)
        # create state ternary to display if current collateral is out of bounds
        state = 0
        if amount < buffer_min:  # too little collateral
            state = -1
        elif amount > buffer_max:  # too much collateral
            state = 1
        positions[idx]["collateral"]["state"] = state

    pprint(positions)
    return positions


def update_call(auth, position):
    """
    margin position["delta_collateral"] is published on the blockchain
    """
    order = {
        "edicts": [
            {
                "op": "call",
                "debt_delta": 0,
                "collateral_delta": position["collateral"]["delta"],
                "tcr": position["collateral"]["mcr"] + 0.01,
            }
        ],
        "header": {
            "asset_id": position["debt"]["id"],
            "currency_id": position["collateral"]["id"],
            "asset_precision": position["debt"]["precision"],
            "currency_precision": position["collateral"]["precision"],
            "account_id": auth["account_id"],
            "account_name": auth["account_name"],
            "wif": auth["wif"],
        },
        "nodes": bitshares_nodes(),
    }

    broker(order)


def main():
    """
    Login then begin Collateral Control Event Loop
    """

    print("\033c")
    # collect user name and wif
    # set buffer
    # set refresh
    authenticated = False
    while not authenticated:

        rpc = wss_handshake()
        auth, call_buffer = user_login()
        account_id = rpc_lookup_accounts(rpc, auth)
        auth["account_id"] = account_id
        authenticated = authenticate(auth)

        try:
            rpc.close()
        except Exception:
            pass

    while 1:
        print("\033c")
        print(logo())
        start = time.time()
        try:
            # begin a remote procedure call with secure websocket
            rpc = wss_handshake()
            # make api call for active margin positions
            positions = get_margin_positions(rpc, auth["account_name"])
            # get asset name and precision, convert to human read, calculate collateral ratio
            positions = personal_collateral_ratio(rpc, positions)
            # add latest market price and feed price
            positions = get_market_feed(rpc, positions)
            # add latest published feed price, mcr, etc.
            positions = get_settlement_feed(rpc, positions)
            # calculate the minimum collateral for the debt held
            # add in the user specified constant buffer
            positions = check_buffer(call_buffer, positions)
            # for each call position: if I have inadequate collateral: add more
            for position in positions:
                print("")
                print(
                    "debt          ",
                    position["debt"]["amount"],
                    position["debt"]["symbol"],
                )
                print(
                    "collateral    ",
                    position["collateral"]["amount"],
                    position["collateral"]["symbol"],
                )
                print("one to one    ", position["collateral"]["one_to_one"])
                print("maintenance   ", position["collateral"]["maintenance"])
                print("min buffer    ", position["collateral"]["buffer_min"])
                print("mid buffer    ", position["collateral"]["buffer_mid"])
                print("max buffer    ", position["collateral"]["buffer_max"])
                print("delta to mid  ", position["collateral"]["delta"])
                print("state         ", position["collateral"]["state"])
            if auth["wif"]:
                for position in positions:
                    # in the event the position collateral is out of bounds
                    if abs(position["collateral"]["state"]):
                        # return the collateral amount to the middle of the road
                        update_call(auth, position)
            delay = call_buffer["buffer_seconds"]
            print(f"Current time {time.ctime()}")
            print(f"Next update at {time.ctime(time.time()+delay)}")
            time.sleep(delay)
        except Exception:
            print(traceback.format_exc())
            time.sleep(10)
            continue
    try:
        rpc.close()
    except Exception:
        pass

    elapsed = time.time() - start
    if elapsed < (call_buffer["buffer_refresh"]):
        time.sleep(call_buffer["buffer_refresh"] - elapsed)


if __name__ == "__main__":

    main()
