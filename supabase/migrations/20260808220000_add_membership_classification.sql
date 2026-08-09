-- Migration 004: Add membership classification to members
--
-- The columns are initially nullable so existing member records
-- are not forced into a classification before we have reviewed them.

ALTER TABLE members
    ADD COLUMN membership_class_id bigint,
    ADD COLUMN membership_status_id bigint,
    ADD COLUMN full_member_type_id bigint;

ALTER TABLE members
    ADD CONSTRAINT members_membership_class_id_fkey
        FOREIGN KEY (membership_class_id)
        REFERENCES membership_classes(id);

ALTER TABLE members
    ADD CONSTRAINT members_membership_status_id_fkey
        FOREIGN KEY (membership_status_id)
        REFERENCES membership_statuses(id);

ALTER TABLE members
    ADD CONSTRAINT members_full_member_type_id_fkey
        FOREIGN KEY (full_member_type_id)
        REFERENCES full_member_types(id);
