from sqlalchemy import ForeignKey, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy import event, create_engine, func
from sqlalchemy.orm import declarative_base, relationship, joinedload, sessionmaker

from datetime import datetime, timedelta, timezone
import game
from exceptions import InsufficientBalanceException, NoGamblerException

from settings import LEVELS
LEVELS:list[dict]
#    "level": 1,
#    "daily": 0.02,
#    "next_xp": 30,
#    "total_xp": 0


Base = declarative_base()

# Database Models
class Gambler(Base):
    __tablename__ = 'gamblers'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    balance = Column(Float, default=100)
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    daily = Column(Float, default=0.02)
    daily_cooldown = Column(DateTime(timezone=True), default=datetime.now())
    default_bet_amount = Column(Float, default=1.00)

    # Relationship to bets
    bets = relationship("Bet", back_populates="gambler")
    
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

# Database Setup
DATABASE_URL = "sqlite:///roulette_game.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
Base.metadata.create_all(engine)
session = Session()

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