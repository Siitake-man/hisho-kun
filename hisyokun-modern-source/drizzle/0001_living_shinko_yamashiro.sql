CREATE TABLE `categories` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`name` varchar(100) NOT NULL,
	`color` varchar(7) NOT NULL DEFAULT '#D4A574',
	`icon` varchar(50) DEFAULT 'calendar',
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `categories_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `events` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`categoryId` int,
	`title` varchar(200) NOT NULL,
	`description` text,
	`startTime` bigint NOT NULL,
	`endTime` bigint,
	`isAllDay` boolean NOT NULL DEFAULT false,
	`recurrenceType` enum('once','yearly_date','yearly_weekday','monthly_date','monthly_end','monthly_weekday','biweekly','weekly','daily') NOT NULL DEFAULT 'once',
	`recurrenceRule` json,
	`recurrenceEndDate` bigint,
	`color` varchar(7),
	`googleEventId` varchar(255),
	`googleCalendarId` varchar(255),
	`lastSyncedAt` timestamp,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `events_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `google_calendar_sync` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`accessToken` text,
	`refreshToken` text,
	`tokenExpiresAt` bigint,
	`calendarIds` json,
	`syncEnabled` boolean NOT NULL DEFAULT true,
	`lastSyncAt` timestamp,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `google_calendar_sync_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `notifications` (
	`id` int AUTO_INCREMENT NOT NULL,
	`eventId` int NOT NULL,
	`userId` int NOT NULL,
	`minutesBefore` int NOT NULL DEFAULT 30,
	`isEnabled` boolean NOT NULL DEFAULT true,
	`isSent` boolean NOT NULL DEFAULT false,
	`sentAt` timestamp,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `notifications_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `sticky_notes` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`content` text NOT NULL,
	`color` varchar(7) NOT NULL DEFAULT '#FFFACD',
	`positionX` int DEFAULT 100,
	`positionY` int DEFAULT 100,
	`width` int DEFAULT 200,
	`height` int DEFAULT 150,
	`zIndex` int DEFAULT 1,
	`isMinimized` boolean NOT NULL DEFAULT false,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `sticky_notes_id` PRIMARY KEY(`id`)
);
