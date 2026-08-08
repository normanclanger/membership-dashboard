-- Migration 001: baseline schema
--
-- This describes the existing database as of 2026-08-08.
-- IMPORTANT: This migration must NOT be run against the existing
-- database. The existing database is already at this schema state.
--
-- It is intended to be used to create a fresh database if required.

CREATE TABLE districts (
    id bigint PRIMARY KEY,
    code varchar NOT NULL UNIQUE,
    name varchar NOT NULL,
    active boolean DEFAULT true
);

CREATE TABLE towers (
    id bigint PRIMARY KEY,
    tower_name varchar NOT NULL,
    district_id bigint NOT NULL,
    active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_tower_district
        FOREIGN KEY (district_id)
        REFERENCES districts(id)
);

CREATE TABLE members (
    id bigint PRIMARY KEY,
    membership_number text NOT NULL UNIQUE,
    first_name text NOT NULL,
    surname text NOT NULL,
    tower_id bigint,

    CONSTRAINT members_tower_id_fkey
        FOREIGN KEY (tower_id)
        REFERENCES towers(id)
);
