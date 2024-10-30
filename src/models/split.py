from .database.db import db


class Split(db.Model):
    __tablename__ = "split"

    id = db.Column(db.Integer, primary_key=True, index=True)
    recordId = db.Column(db.Integer, db.ForeignKey("record.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    personId = db.Column(db.Integer, db.ForeignKey("person.id"), nullable=False)
    isPaid = db.Column(db.Boolean, nullable=False, default=False)
    
    record = db.relationship("Record", foreign_keys=[recordId], back_populates="splits")
    person = db.relationship("Person", foreign_keys=[personId], back_populates="splits")