"""Initial Migration

Revision ID: 6d505584380c
Revises: 
Create Date: 2025-01-21 19:52:17.217379

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6d505584380c'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('repository',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('default_branch', sa.String(length=50), nullable=False),
    sa.Column('stars', sa.Integer(), nullable=False),
    sa.Column('forks', sa.Integer(), nullable=False),
    sa.Column('open_issues', sa.Integer(), nullable=False),
    sa.Column('latest_commit_date', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('repository')
    # ### end Alembic commands ###
