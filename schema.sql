

CREATE TABLE IF NOT EXISTS riders (
    number INT PRIMARY KEY,
    name   VARCHAR(50),
    team   VARCHAR(50),
    maker  VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS laps (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    rider_number INT,
    lap          INT,
    lap_time     DECIMAL(6,3),
    sector1      DECIMAL(6,3),
    sector2      DECIMAL(6,3),
    sector3      DECIMAL(6,3),
    FOREIGN KEY (rider_number) REFERENCES riders(number)
);

CREATE TABLE IF NOT EXISTS personal_best_log (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    rider_number INT,
    lap          INT,
    lap_time     DECIMAL(6,3),
    logged_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rider_number) REFERENCES riders(number)
);


DELIMITER //


DROP TRIGGER IF EXISTS trg_personal_best//
CREATE TRIGGER trg_personal_best
AFTER INSERT ON laps
FOR EACH ROW
BEGIN
    DECLARE prev_best DECIMAL(6,3);

    SELECT MIN(lap_time) INTO prev_best
      FROM laps
     WHERE rider_number = NEW.rider_number
       AND id <> NEW.id;

    IF prev_best IS NOT NULL AND NEW.lap_time < prev_best THEN
        INSERT INTO personal_best_log (rider_number, lap, lap_time)
        VALUES (NEW.rider_number, NEW.lap, NEW.lap_time);
    END IF;
END//


DROP PROCEDURE IF EXISTS rider_report//
CREATE PROCEDURE rider_report(IN p_number INT)
BEGIN
    SELECT lap, lap_time, sector1, sector2, sector3
      FROM laps
     WHERE rider_number = p_number
     ORDER BY lap;
END//


DELIMITER ;


CREATE OR REPLACE VIEW leaderboard AS
SELECT  r.number,
        r.name,
        r.team,
        COUNT(l.id)     AS laps_done,
        SUM(l.lap_time) AS total_time,
        MIN(l.lap_time) AS best_lap
FROM       riders r
LEFT JOIN  laps   l ON l.rider_number = r.number
GROUP BY   r.number, r.name, r.team
ORDER BY   total_time;
