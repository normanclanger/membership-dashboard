-- Migration 003: Seed membership classes
--
-- Migration 002 created the membership_classes table but
-- did not include the initial reference data.

INSERT INTO membership_classes (code, name)
VALUES
    ('FULL', 'Full member'),
    ('ASSOCIATE', 'Associate member'),
    ('NRLM', 'Non-resident life member');
