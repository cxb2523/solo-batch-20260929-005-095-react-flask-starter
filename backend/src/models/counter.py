from sqlalchemy import UniqueConstraint, case, func
from sqlalchemy.exc import IntegrityError

from src.models.base import BaseModel, db


class CounterEvent(BaseModel):

    __tablename__ = 'counter_event'

    task_id = db.Column(db.String(64), nullable=False, index=True)
    counter_id = db.Column(db.Integer, db.ForeignKey('counter.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint('task_id', 'counter_id', name='uq_counter_event_task_counter'),
    )


class Counter(BaseModel):

    count = db.Column(db.Integer, default=0, nullable=False)
    label = db.Column(db.String(), nullable=False, unique=True, index=True)

    RESET_THRESHOLD = 1000000000

    @classmethod
    def snapshot(cls, label='Test'):
        counter = cls.get(label=label)
        return counter.count if counter else 0

    @classmethod
    def apply_task_increment(cls, task_id, amount=1, label=None):
        counters = [cls.get(label=label)] if label is not None else cls.list()
        counters = [counter for counter in counters if counter is not None]
        if not counters:
            db.session.rollback()
            return cls.snapshot(label=label) if label is not None else 0, False

        if CounterEvent.query.filter_by(task_id=task_id).first() is not None:
            db.session.rollback()
            if label is not None:
                result = cls.snapshot(label=label)
            else:
                result = db.session.query(func.max(Counter.count)).scalar() or 0
            return result, False

        next_count = case(
            [(Counter.count + amount > cls.RESET_THRESHOLD, 0)],
            else_=Counter.count + amount
        )

        try:
            db.session.query(Counter).filter(
                Counter.id.in_([counter.id for counter in counters])
            ).update(
                {Counter.count: next_count},
                synchronize_session=False
            )
            for counter in counters:
                db.session.add(CounterEvent(
                    task_id=task_id,
                    counter_id=counter.id,
                    amount=amount
                ))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            if CounterEvent.query.filter_by(task_id=task_id).first() is not None:
                if label is not None:
                    result = cls.snapshot(label=label)
                else:
                    result = db.session.query(func.max(Counter.count)).scalar() or 0
                return result, False
            raise

        if label is not None:
            result = cls.snapshot(label=label)
        else:
            result = db.session.query(func.max(Counter.count)).scalar() or 0
        return result, True

    @classmethod
    def get_or_create(cls, label):
        counter = cls.get(label=label)
        if counter is not None:
            return counter

        counter = Counter(label=label, count=0)
        counter.generate_unique_uuid()
        db.session.add(counter)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            counter = cls.get(label=label, exception=True)
        return counter

    def reset(self):
        try:
            db.session.query(CounterEvent).filter_by(counter_id=self.id).delete()
            db.session.query(Counter).filter_by(id=self.id).update(
                {Counter.count: 0},
                synchronize_session=False
            )
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
