<?php
/** Booking rules; deliberately independent of WordPress and storage. */
declare(strict_types=1);

final class Empire_Yard_Booking_Rules {
    public const ACTIVE = ['held', 'confirmed'];
    public const SERVICES = ['repair', 'inspection', 'tyres', 'maintenance'];
    private const TRANSITIONS = [
        'held' => ['confirmed', 'cancelled'],
        'confirmed' => ['completed', 'cancelled'],
        'cancelled' => [],
        'completed' => [],
    ];

    /** UTC instants and IANA zone; reject invalid DST-local times instead of guessing. */
    public static function slot(string $date, string $time, int $minutes, string $zone): array {
        if (!preg_match('/^\d{4}-\d{2}-\d{2}$/D', $date) ||
            !preg_match('/^\d{2}:\d{2}$/D', $time) || $minutes < 15 || $minutes > 480 || $minutes % 15 !== 0 ||
            !in_array($zone, timezone_identifiers_list(), true)) {
            throw new InvalidArgumentException('Invalid booking date, duration or IANA time zone');
        }
        $tz = new DateTimeZone($zone);
        $wall = $date . ' ' . $time;
        $start = DateTimeImmutable::createFromFormat('!Y-m-d H:i', $wall, $tz);
        $errors = DateTimeImmutable::getLastErrors();
        if ($start === false || ($errors !== false && ($errors['warning_count'] || $errors['error_count'])) ||
            $start->format('Y-m-d H:i') !== $wall) {
            throw new InvalidArgumentException('Nonexistent or malformed local time');
        }
        // A repeated wall clock hour at a DST fall-back has two real instants.
        // Decline both until a staff member supplies an unambiguous slot.
        $epoch = $start->getTimestamp();
        foreach ($tz->getTransitions($epoch - 172800, $epoch + 172800) ?: [] as $transition) {
            $at = (int) $transition['ts'];
            $before = (new DateTimeImmutable('@' . ($at - 1)))->setTimezone($tz)->getOffset();
            $after = (new DateTimeImmutable('@' . $at))->setTimezone($tz)->getOffset();
            if ($after < $before) {
                $localBefore = $at + $after;
                $localAfter = $at + $before;
                $wallSeconds = (new DateTimeImmutable($wall, new DateTimeZone('UTC')))->getTimestamp();
                if ($wallSeconds >= $localBefore && $wallSeconds < $localAfter) {
                    throw new InvalidArgumentException('Ambiguous DST local time');
                }
            }
        }
        $end = new DateTimeImmutable('@' . ($epoch + $minutes * 60));
        return [
            'start_utc' => $start->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s'),
            'end_utc' => $end->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s'),
            'timezone' => $zone,
        ];
    }

    /** Half-open intervals allow back-to-back bookings. */
    public static function overlaps(string $aStart, string $aEnd, string $bStart, string $bEnd): bool {
        return $aStart < $bEnd && $bStart < $aEnd;
    }

    public static function conflicts(array $candidate, array $existing): bool {
        if (!in_array($candidate['status'] ?? '', self::ACTIVE, true) ||
            !in_array($existing['status'] ?? '', self::ACTIVE, true) ||
            ($candidate['bay'] ?? '') !== ($existing['bay'] ?? '')) {
            return false;
        }
        return self::overlaps(
            $candidate['start_utc'], $candidate['end_utc'],
            $existing['start_utc'], $existing['end_utc']
        );
    }

    public static function canTransition(string $from, string $to): bool {
        return in_array($to, self::TRANSITIONS[$from] ?? [], true);
    }
}
