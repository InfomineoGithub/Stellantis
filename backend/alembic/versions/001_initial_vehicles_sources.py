"""initial_vehicles_sources

Revision ID: 001
Revises:
Create Date: 2026-04-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'vehicles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('manufacturer', sa.String(), nullable=False),
        sa.Column('model_name', sa.String(), nullable=False),
        sa.Column('vehicle_class', sa.Enum('compact', 'midsize', 'full_size', 'luxury', 'economy', name='vehicleclass'), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('body_type', sa.Enum('sedan', 'suv', 'hatchback', 'coupe', 'convertible', 'pickup', 'van', name='bodytype'), nullable=False),
        sa.Column('transmission', sa.Enum('manual', 'automatic', 'cvt', name='transmission'), nullable=False),
        sa.Column('fuel_type', sa.Enum('gasoline', 'diesel', 'electric', 'hybrid', 'phev', 'bev', name='fueltype'), nullable=False),
        sa.Column('thumbnail_url', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('manufacturer', 'model_name', 'year'),
    )
    op.create_table(
        'sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_type', sa.Enum('web_url', 'youtube_video', 'pdf', name='sourcetype'), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url'),
    )
    op.create_table(
        'vehicle_sources',
        sa.Column('vehicle_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('vehicle_id', 'source_id'),
    )


def downgrade() -> None:
    op.drop_table('vehicle_sources')
    op.drop_table('sources')
    op.drop_table('vehicles')
    op.execute('DROP TYPE IF EXISTS vehicleclass')
    op.execute('DROP TYPE IF EXISTS bodytype')
    op.execute('DROP TYPE IF EXISTS transmission')
    op.execute('DROP TYPE IF EXISTS fueltype')
    op.execute('DROP TYPE IF EXISTS sourcetype')
