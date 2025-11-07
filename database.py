import os
import random
import time
from dotenv import load_dotenv, set_key
import requests
from sqlalchemy import ForeignKey, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy import event, create_engine, func
from sqlalchemy.orm import declarative_base, relationship, joinedload, sessionmaker

from datetime import datetime, timedelta, timezone
import game
from exceptions import InsufficientBalanceException, NoGamblerException, TradeURLMissingException

from settings import LEVELS
import settings
LEVELS:list[dict]
#    "level": 1,
#    "daily": 0.02,
#    "next_xp": 30,
#    "total_xp": 0

our_trade_urls = ["https://steamcommunity.com/tradeoffer/new/?partner=293384199&token=nB1gAF-B"]

Base = declarative_base()

# Database Models
class Gambler(Base):
    __tablename__ = 'gamblers'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    balance = Column(Float, default=0)
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    daily = Column(Float, default=10.00)
    daily_cooldown = Column(DateTime(timezone=True), default=datetime.now())
    default_bet_amount = Column(Float, default=1.00)
    trade_url = Column(String, nullable=True)

    # Relationship to bets
    bets = relationship("Bet", back_populates="gambler")
    items = relationship("Item", back_populates="gambler")
    
    def __repr__(self):
        return f"Name={self.name} (Lvl.{self.level}), Balance={self.balance}"
    
    def __lt__(self, other):
        if self.balance != other.balance:
            return self.balance < other.balance
        return sum(bet.amount for bet in self.bets) < sum(bet.amount for bet in other.bets)

    def __le__(self, other):
        return self < other or self == other

    def __gt__(self, other):
        return not self <= other

    def __ge__(self, other):
        return not self < other

    def __eq__(self, other):
        return self.balance == other.balance and sum(bet.amount for bet in self.bets) == sum(bet.amount for bet in other.bets)

    def __ne__(self, other):
        return not self == other

class Item(Base):
    __tablename__ = 'items'
    id = Column(Integer, nullable=False, primary_key=True)
    name = Column(String)
    exterior = Column(String)
    float_val = Column(Float, default=None)
    is_tradable = Column(Boolean)
    tradable_date = Column(DateTime, default=None)
    inspect_link = Column(String)
    image_url = Column(String)
    buff_price = Column(Float, nullable=True)
    last_update = Column(DateTime, default=datetime.now(timezone.utc))

    # Foreign key to link items to gamblers
    gambler_id = Column(Integer, ForeignKey('gamblers.id'), nullable=False)

    # Relationship back to gambler
    gambler = relationship("Gambler", back_populates="items")
    # Comparison methods based on buff_price
    def __lt__(self, other):
        if isinstance(other, Item):
            return self.buff_price < other.buff_price
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, Item):
            return self.buff_price <= other.buff_price
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, Item):
            return self.buff_price > other.buff_price
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, Item):
            return self.buff_price >= other.buff_price
        return NotImplemented

    def __eq__(self, other):
        if isinstance(other, Item):
            return self.buff_price == other.buff_price
        return NotImplemented

    def __ne__(self, other):
        if isinstance(other, Item):
            return self.buff_price != other.buff_price
        return NotImplemented

class Round(Base):
    __tablename__ = 'rounds'

    id = Column(String, primary_key=True)
    result_num = Column(Integer, nullable=False)
    result_color = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=True, default=func.now())

    # Relationship to bets
    bets = relationship("Bet", back_populates="round")

    def __repr__(self):
        return f"ID={self.id} Result={self.result_color}_{self.result_num} ({self.timestamp})"

class Bet(Base):
    __tablename__ = 'bets'

    id = Column(String, primary_key=True)
    amount = Column(Float, nullable=False)
    bet_on = Column(String)
    is_correct = Column(Boolean)
    old_balance = Column(Float, nullable=False)
    new_balance = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=True, default=func.now())

    gambler_id = Column(Integer, ForeignKey('gamblers.id'), nullable=False)
    round_id = Column(Integer, ForeignKey('rounds.id'), nullable=False)

    gambler = relationship("Gambler", back_populates="bets")
    round = relationship("Round", back_populates="bets")

    def __repr__(self):
        gambler_name = getattr(self.gambler, "name", "Unknown")
        return f"Bet Gambler={gambler_name}, Amount={self.amount}, Round={self.round_id}"


def generate_unique_id(prefix="id"):
    import uuid
    return f"{prefix}-{uuid.uuid4()}"

@event.listens_for(Bet, "before_insert")
def set_bet_id(mapper, connection, target):
    if not target.id:
        target.id = generate_unique_id(prefix="bet")

VOLUME_DIR = "/database"
DB_NAME = "roulette_game.db"
DATABASE_PATH = os.path.join(VOLUME_DIR, DB_NAME)
os.makedirs(VOLUME_DIR, exist_ok=True)
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# The rest of your code remains the same
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
Base.metadata.create_all(engine)
session = Session()

print(f"Database connected at: {DATABASE_URL}")

# Gambler CRUD Operations
def create_gambler(id, name, balance=100, xp=0, level=1, daily=0.02, default_bet_amount=1):  
    try:
        gambler = Gambler(id=id, name=name, balance=balance, xp=xp, level=level, daily=daily, default_bet_amount=default_bet_amount)
        session.add(gambler)
        session.commit()
        print(f"Gambler {name} created with ID={gambler.id}")
        return gambler
    except Exception as e:
        session.rollback()
        print(f"Error creating gambler: {e}")

def get_gambler_by_id(gambler_id: int) -> Gambler:
    try:
        gambler = session.query(Gambler).options(joinedload(Gambler.bets)).filter_by(id=gambler_id).first()
        if gambler:
            return gambler
        else:
            raise NoGamblerException("You are not registered yet. Please click on the `Register` button and start playing.")
    except Exception as e:
        print(f"Database Error! get_gambler_by_id: {e}")

def update_daily_cooldown(gambler_id: int): 
    try:
        gambler = get_gambler_by_id(gambler_id)
        gambler.daily_cooldown = datetime.now().replace(microsecond=0) + timedelta(days=1)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error updating daily reward cooldown: {e}")
        raise e
    
def update_gambler_balance(gambler_id:int, update_balance:float):
    try:
        gambler = get_gambler_by_id(gambler_id)
        gambler.balance += update_balance
        gambler.balance = round(gambler.balance, 2)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error updating balance: {e}")

def delete_gambler(gambler_id:int):
    try:
        gambler = get_gambler_by_id(gambler_id)
        session.delete(gambler)
        session.commit()
        print(f"Gambler ID={gambler_id} deleted")
    except Exception as e:
        session.rollback()
        print(f"Error deleting gambler: {e}")

def set_gambler_bet_amount(gambler_id:int, bet_amount:float):
    try:
        gambler = get_gambler_by_id(gambler_id)
        gambler.default_bet_amount = bet_amount
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error setting gambler's new bet amount: {e}")

def gambler_update_xp(gambler_id:int, xp:int):
    try:
        gambler = get_gambler_by_id(gambler_id)
        gambler.xp += xp
        gambler.xp = int(gambler.xp)
        
        while gambler.xp >= LEVELS[gambler.level+1].get("total_xp"):
            gambler.level = LEVELS[gambler.level+1].get("level")

        gambler.daily = LEVELS[gambler.level].get("daily")
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error updating xp: {e}")

def set_trade_url(gambler_id:int, url:str) -> str:
    try:
        gambler = get_gambler_by_id(gambler_id)
        gambler.trade_url = url
        session.commit()
        return gambler.trade_url
    except Exception as e:
        session.rollback()
        print(f"Error setting the trade url: {e}")
        raise e
    
# Round CRUD Operations
def create_round(round_id:str, round_result:int) -> Round:
    try:
        round_entry = Round(
            id = round_id,
            result_num = round_result,
            result_color = game.NUMBER_COLOR_MAPPING.get(round_result)
        )
        session.add(round_entry)
        session.commit()
        return round_entry
    except Exception as e:
        session.rollback()
        print(f"Error creating round: {e}")

def get_round_by_id(round_id) -> Round:
    try:
        round_entry = session.query(Round).filter_by(id=round_id).first()
        return round_entry
    except Exception:
        return None

def get_last_round() -> Round: 
    try:
        round_entry = session.query(Round).order_by(Round.timestamp.desc()).first()
        return round_entry
    except Exception:
        return None


# Bet CRUD Operations
def create_bet(gambler:Gambler, round:Round, amount:float, bet_on:str) -> Bet:
    if amount > gambler.balance:
        raise InsufficientBalanceException(f"You do not have enough credits.\nBalance: **${gambler.balance}**\nBet: **${amount}**")
    try:
        is_correct = round.result_color == bet_on
        if is_correct:
            multiplier = (
                game.RED_MULTIPLIER if bet_on == game.Results.RED else
                game.BLACK_MULTIPLIER if bet_on == game.Results.BLACK else
                game.GREEN_MULTIPLIER if bet_on == game.Results.GREEN else 0
            )
        else:
            multiplier = 0
        new_bet = Bet(
            amount = amount,
            bet_on = bet_on,
            is_correct = is_correct,
            old_balance = gambler.balance,
            new_balance = gambler.balance + (multiplier-1)*amount,
            gambler_id = gambler.id,
            round_id = round.id,
        )
        session.add(new_bet)
        session.commit()
        return new_bet
    except Exception as e:
        session.rollback()
        print(f"Error creating bet: {e}")

def get_bet_of_gambler_by_round_id(gambler_id:int, round_id:int) -> Bet:
    bet = session.query(Bet).filter(Bet.gambler_id==gambler_id).filter(Bet.round_id==round_id).first()
    return bet

def process_bets():
    current_round:Round = get_last_round()
    bets:list[Bet] = get_all_bets_by_round_id(current_round.id)
    for bet in bets:
        if bet.is_correct:
            multiplier = (
                game.RED_MULTIPLIER if bet.bet_on == game.Results.RED else
                game.BLACK_MULTIPLIER if bet.bet_on == game.Results.BLACK else
                game.GREEN_MULTIPLIER if bet.bet_on == game.Results.GREEN else 0
            )
            update_gambler_balance(bet.gambler_id, bet.amount*multiplier)


# Item CRUD Operations
def get_items_by_gambler(gambler:Gambler) -> list[Item]:
    return session.query(Item).filter(Item.gambler == gambler).all()

def refresh_user_items(gambler_id: int):
    gambler = session.query(Gambler).filter(Gambler.id == gambler_id).first()
    trade_url = gambler.trade_url
    if not trade_url:
        raise TradeURLMissingException("You have not set your trade URL yet. Visit https://steamcommunity.com/id/example/tradeoffers/privacy#trade_offer_access_url to get it and use /trade_url command to save.")

    baseid = 76561197960265728  # Base Steam ID for conversion
    base_url, params = trade_url.split("?")
    query_params = dict(param.split("=") for param in params.split("&"))
    steam_partner_id = query_params.get("partner")

    try:
        user_id = str(baseid + int(steam_partner_id))
        inventory_url = f"https://steamcommunity.com/inventory/{user_id}/730/2"
        items_steam_inv = requests.get(inventory_url).json().get("descriptions")
        steam_item_names = {item.get("market_hash_name") for item in items_steam_inv}
        
        # Delete the items that no longer in the inventory
        current_items = {item.name: item for item in session.query(Item).filter(Item.gambler_id == gambler_id).all()}
        no_longer_exist_items = [current_item for current_item in current_items.values() if current_item.name not in steam_item_names]
        for item in no_longer_exist_items:
            session.delete(item)

        # Add or update items from the Steam inventory
        for item_data in items_steam_inv:
            name: str = item_data.get("market_hash_name")
            existing_item = current_items.get(name)

            # Check if the item exists and if it was updated within the last 24 hours
            if existing_item and existing_item.last_update and (datetime.now() - existing_item.last_update) < timedelta(hours=24):
                print(f"Skipping item *{name}* of *{gambler.name}* as it was updated within the last 24 hours.")
                continue

            # Delete the existing item if it's not updated within 24 hours
            if existing_item:
                session.delete(existing_item)

            try:
                item_buff_id = ITEM_ID_DICT[name]
                print(f"{name} requested Buff Price! {datetime.now(timezone.utc)}")
                buff_price_ls, buff_price_hb = getBuffDataByItemID(item_buff_id)
                buff_price_ls *= 1.03
                buff_price_hb *= 0.95
            except:
                buff_price_ls, buff_price_hb = None, None

            shortname = item_data.get("name")
            if name.startswith(shortname):
                exterior = name[len(shortname):].strip().replace("(", "").replace(")", "")
            else:
                exterior = None
            is_tradable = item_data.get("tradable")
            image_url = "https://steamcommunity-a.akamaihd.net/economy/image/" + item_data.get("icon_url")
            inspect_link = None
            try:
                inspect_link = item_data.get("actions")[0].get("link")
            except Exception:
                pass

            tradable_date = None
            try:
                owner_descriptions = item_data.get("owner_descriptions", [])
                if owner_descriptions and len(owner_descriptions) > 1:
                    tradable_date = owner_descriptions[1].get("value")
            except Exception:
                pass

            # Create the new item
            new_item = Item(
                name=name,
                exterior=exterior,
                is_tradable=is_tradable,
                image_url=image_url,
                buff_price=buff_price_hb,
                tradable_date=tradable_date,
                inspect_link=inspect_link,
                gambler=gambler,
                last_update=datetime.now(timezone.utc)  # Set the current time as the last update
            )
            session.add(new_item)

        session.commit()
        print("Items refreshed successfully.")

    except Exception as e:
        session.rollback()
        print(f"Error fetching the items. {e}")

# Utility Functions
def get_all_gamblers() -> list[Gambler]:
    gamblers = session.query(Gambler).all()
    return gamblers

def get_all_rounds() -> list[Round]:
    rounds = session.query(Round).all()
    return rounds

def get_last_x_rounds(num: int) -> list[Round]:
    try:
        rounds = session.query(Round).order_by(Round.timestamp.desc()).limit(num).all()
        return rounds[::-1]
    except Exception as e:
        print(f"Error fetching last {num} rounds: {e}")
        return []

def get_gambler_total_bet(gambler_id) -> float:
    all_bets = session.query(Bet).filter(Bet.gambler_id==gambler_id).all()
    return sum([bet.amount for bet in all_bets])

def get_round_count() -> int:
    return session.query(Round).count()

def get_all_bets_by_round_id(round_id:int) -> list[Bet]:   
    bets = session.query(Bet).filter(Bet.round_id==round_id).all()
    return bets


# ---------------------------- BUFF PRICE ---------------------------- #
RETRY = 4
HEADERS = settings.buff_headers
PARAMS = settings.buff_params
PROXIES = None
LS_url = "https://buff.163.com/api/market/goods/sell_order"
HB_url = "https://buff.163.com/api/market/goods/buy_order"
with open("buffids.txt", "r", encoding="utf8") as f:
    lines = f.readlines()

ITEM_ID_DICT = {line.split(";")[1].strip():line.split(";")[0] for line in lines}
def getCNY_USD() -> float:
        load_dotenv()
        f = os.getenv("YUANUSD")
        rate, date = f.split(",")
        
        dt_object = datetime.strptime(date, "%d/%m/%Y")
        if dt_object < datetime.now():
            try:
                url = "https://api.exchangerate-api.com/v4/latest/CNY"
                response = requests.get(url)
                data = response.json()
                rate = float(data["rates"]["USD"])
                formatted_date = datetime.now().strftime("%d/%m/%Y")
                set_key(".env", "YUANUSD", f"{str(rate)},{formatted_date}")
            except Exception as e:
                print(e)
        return rate
YUANUSD = getCNY_USD()

def getBuffDataByItemID(itemid):
    PARAMS["goods_id"] = str(itemid)
    for try_count in range(RETRY):
        try:
            sellResponseRequest = requests.get(LS_url, params=PARAMS, headers=HEADERS, proxies=PROXIES, timeout=5)
            sellResponse = sellResponseRequest.json()["data"]["items"]
            break
        except Exception as e:
            if sellResponseRequest.status_code == 429:
                print("Too many requests")
                time.sleep(random.randint(1,3))
            continue

    for try_count in range(RETRY):
        try:
            buyResponseRequest = requests.get(HB_url, params=PARAMS, headers=HEADERS, proxies=PROXIES, timeout=5)
            buyResponse = buyResponseRequest.json()["data"]["items"]
            break
        except Exception as e:
            if buyResponseRequest.status_code == 429:
                print("Too many requests")
                time.sleep(random.randint(1,3))
            continue

    try:
        lowestSell = round(float(sellResponse[0].get("price"))*YUANUSD, 2)
    except Exception:
        lowestSell = None
    try:
        highestBuy = round(float(buyResponse[0].get("price"))*YUANUSD, 2)
    except Exception:
        highestBuy = None

    return (lowestSell, highestBuy)