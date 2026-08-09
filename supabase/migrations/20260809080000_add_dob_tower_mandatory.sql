-- Migration 005: Add date of birth and make tower mandatory

ALTER TABLE members
    ADD COLUMN date_of_birth date;

ALTER TABLE members
    ALTER COLUMN tower_id SET NOT NULL;
