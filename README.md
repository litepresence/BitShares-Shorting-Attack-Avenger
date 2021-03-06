<p align="center"> 
<img src="https://imgur.com/4hSbRja.jpg">	
<img src="https://imgur.com/ygdhTpw.jpg">
</p>


BitShares "Shorting Attack" Avenger ^TM

pre-alpha

To Run
=======================================
    python3 Avenger.py

User Enters
=======================================
    Account Name and Wif
    Minimum and Maximum Buffer over MCR; eg. 20% to 30% over MCR
    Update Frequency; eg. every 10 minutes

Script Maintains Collateral
=======================================
    Shorting Attacks Avenger ensures you always have adequate collateral backing each debt
    it also ensures you do not have too much collateral backing your debt
    in either case, when out of bounds
    it returns your collateral to the middle of the band specified

Dependencies:
=======================================
    Collateral control leverages dex_manual_signing to perform ecdsa, it can be run in an
    extinction-event environment.  Else you will need minimum of

    python3.7+ and pip3 modules: ecdsa, secp256k1, websocket-client

    built and tested on linux mint 19

Features Todo:
=======================================
    30+ Day app runtime durability
    edit naming conventions, pylint, pep8
    handle bad user inputs
    improve cli ux with pandas like table view and color terminal

Features Complete:
=======================================

**1) GET OPEN CALL ORDERS**

An initial public api rpc for margin positions returns a list of dicts
you are given asset_id's of the collateral and debt
and the graphene amount of each that you hold
but no actual price data
in human terms the response is murky, but this is a full accounting of our debts

```
    [
    {'id',
    'borrower',
    'collateral', # graphene amount
    'debt': , # graphene amount
    'call_price':
        {'base': {'asset_id'},   # base collateral asset_id
        'quote': {'asset_id'}}}  # quote debt asset i_d
    , ...
    ]
```

**2) GET MORE INFO ON ALL ORDERS**

The script makes this information more useful by making some additional calls:

    get_ticker()                   # last, ask, bid
    get_objects(asset_id)          # asset_name, precision, bitasset_data_id
    get_objects(bitasset_data_id)  # settlement conditions

**3) USER INPUT TO BOT**

It then considers user input upper and lower bound percent buffer above the MCR:


    buffer_max  # maximum collateral held above mcr in percent terms
    buffer_min  # minimum likewise

Such that:  

    (1 < buffer_min < buffer_max < 10)

**4) STATE MACHINE**

If the price gets out of bounds collateral is brought back to:

    buffer_mid  # halfway between user defined buffer_max and buffer_min coeffs of MCR

**5) NORMALIZING**

All amounts are converted from graphene to human readable and rounded to 6 sig figures

**6) API**

The result is stored as a easy to navigate list of positions
each position dictionary contains an "id" and 3 sub dicts:

    [collateral, debt, price]

This is the hocus pocus which makes automated dex collateral management possible
by exposing a human compatible list of dictionaries, of pertinent loan data, to the borrower:

```
    [                               # list of nested position dictionaries
    {
        'id':                       # 1.8.x debt identifier
        ,
        'collateral': {
            'amount':               # user current collateral
            'buffer_max':           # mcr * user specified max buffer
            'buffer_mid':           # (max+min) / 2
            'buffer_min':           # mcr * user specified min buffer
            'current_ratio':        # how many times is debt covered by your collateral
            'delta':                # user collateral from buffer_mid
            'id':                   # 1.3.x asset id
            'maintenance':          # minimum collateral required for maintainance
            'maintenance_ratio':    # from get_objects(bitasset_data_id); the MCR, eg. 1.50
            'one_to_one':           # amount of collateral worth one unit of debt
            'precision':            # get_objects(asset_id) graphene amount convertion
            'state':                # ternary; 0 when collateral in range, -1 low, 1 high
            'symbol':               # eg. BTS
        },
        'debt': {
            'amount':               # user current debt
            'bitasset_data_id':     # 2.4.x from get_objects(asset_id)["bitasset_data_id"]
            'id':                   # 1.3.x asset id
            'precision':            # graphene to human amount conversion
            'symbol':               # eg. HONEST.USD
        },
        'price': {
            'ask':                  # from ticker last
            'bid':                  # from ticker highest bid
            'last':                 # from ticker lowest ask
            'settlement':           # from get_objects(bitasset_data_id)
        },
    }
    ...]
```
The last item to be added to the dictionary is the `position["collateral"]["delta"]`, which is a culmination of all the other data in the dictionary.  `collateral_delta` will be required in the final `Call_order_update` operation, which we are ultimately preparing, to maintain collateral for each margin position.

Execute:
=======================================

    for each margin_position in my open call positions list:

        # if I have too much or too little buffer over the MCR
        if min_buffer > collateral > max_buffer:

            Call_order_update(collateral_delta)
