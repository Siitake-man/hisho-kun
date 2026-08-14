import { int, mysqlEnum, mysqlTable, text, timestamp, varchar, boolean, bigint, json } from "drizzle-orm/mysql-core";

/**
 * Core user table backing auth flow.
 */
export const users = mysqlTable("users", {
  id: int("id").autoincrement().primaryKey(),
  openId: varchar("openId", { length: 64 }).notNull().unique(),
  name: text("name"),
  email: varchar("email", { length: 320 }),
  loginMethod: varchar("loginMethod", { length: 64 }),
  role: mysqlEnum("role", ["user", "admin"]).default("user").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
  lastSignedIn: timestamp("lastSignedIn").defaultNow().notNull(),
});

export type User = typeof users.$inferSelect;
export type InsertUser = typeof users.$inferInsert;

/**
 * Categories for events (color and icon)
 */
export const categories = mysqlTable("categories", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  name: varchar("name", { length: 100 }).notNull(),
  color: varchar("color", { length: 7 }).notNull().default("#D4A574"), // Retro brown default
  icon: varchar("icon", { length: 50 }).default("calendar"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
});

export type Category = typeof categories.$inferSelect;
export type InsertCategory = typeof categories.$inferInsert;

/**
 * Recurrence pattern types matching 秘書くん2's 9 patterns
 */
export const recurrenceTypeEnum = mysqlEnum("recurrenceType", [
  "once",           // 一回きり
  "yearly_date",    // 毎年○月○日
  "yearly_weekday", // 毎年○月第○○曜日
  "monthly_date",   // 毎月○日
  "monthly_end",    // 毎月末
  "monthly_weekday",// 毎月第○○曜日
  "biweekly",       // 隔週○曜日
  "weekly",         // 毎週○曜日
  "daily",          // 毎日
]);

/**
 * Events table - main schedule data
 */
export const events = mysqlTable("events", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  categoryId: int("categoryId"),
  title: varchar("title", { length: 200 }).notNull(),
  description: text("description"),
  
  // Date/time (stored as UTC timestamps in milliseconds)
  startTime: bigint("startTime", { mode: "number" }).notNull(),
  endTime: bigint("endTime", { mode: "number" }),
  isAllDay: boolean("isAllDay").default(false).notNull(),
  
  // Recurrence settings
  recurrenceType: recurrenceTypeEnum.default("once").notNull(),
  recurrenceRule: json("recurrenceRule"), // JSON for complex rules
  recurrenceEndDate: bigint("recurrenceEndDate", { mode: "number" }),
  
  // Display settings
  color: varchar("color", { length: 7 }),
  
  // Google Calendar sync
  googleEventId: varchar("googleEventId", { length: 255 }),
  googleCalendarId: varchar("googleCalendarId", { length: 255 }),
  lastSyncedAt: timestamp("lastSyncedAt"),
  
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
});

export type Event = typeof events.$inferSelect;
export type InsertEvent = typeof events.$inferInsert;

/**
 * Notifications for events
 */
export const notifications = mysqlTable("notifications", {
  id: int("id").autoincrement().primaryKey(),
  eventId: int("eventId").notNull(),
  userId: int("userId").notNull(),
  
  // Notification timing (minutes before event)
  minutesBefore: int("minutesBefore").notNull().default(30),
  
  // Notification status
  isEnabled: boolean("isEnabled").default(true).notNull(),
  isSent: boolean("isSent").default(false).notNull(),
  sentAt: timestamp("sentAt"),
  
  createdAt: timestamp("createdAt").defaultNow().notNull(),
});

export type Notification = typeof notifications.$inferSelect;
export type InsertNotification = typeof notifications.$inferInsert;

/**
 * Sticky notes (付箋) - not tied to specific dates
 */
export const stickyNotes = mysqlTable("sticky_notes", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  content: text("content").notNull(),
  color: varchar("color", { length: 7 }).default("#FFFACD").notNull(), // Light yellow default
  
  // Position for desktop-style display
  positionX: int("positionX").default(100),
  positionY: int("positionY").default(100),
  width: int("width").default(200),
  height: int("height").default(150),
  zIndex: int("zIndex").default(1),
  
  isMinimized: boolean("isMinimized").default(false).notNull(),
  
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
});

export type StickyNote = typeof stickyNotes.$inferSelect;
export type InsertStickyNote = typeof stickyNotes.$inferInsert;

/**
 * Google Calendar sync settings
 */
export const googleCalendarSync = mysqlTable("google_calendar_sync", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  
  // OAuth tokens (encrypted in production)
  accessToken: text("accessToken"),
  refreshToken: text("refreshToken"),
  tokenExpiresAt: bigint("tokenExpiresAt", { mode: "number" }),
  
  // Sync settings
  calendarIds: json("calendarIds"), // Array of calendar IDs to sync
  syncEnabled: boolean("syncEnabled").default(true).notNull(),
  lastSyncAt: timestamp("lastSyncAt"),
  
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
});

export type GoogleCalendarSync = typeof googleCalendarSync.$inferSelect;
export type InsertGoogleCalendarSync = typeof googleCalendarSync.$inferInsert;

/**
 * Recurrence rule JSON structure type
 */
export interface RecurrenceRule {
  // For yearly_date: month (1-12), day (1-31)
  month?: number;
  day?: number;
  
  // For yearly_weekday, monthly_weekday: weekNumber (1-5, -1 for last), weekday (0-6, 0=Sunday)
  weekNumber?: number;
  weekday?: number;
  
  // For biweekly: startDate (to calculate which weeks)
  startDate?: number;
  
  // For weekly: weekdays array [0-6]
  weekdays?: number[];
  
  // Common: interval (e.g., every 2 weeks)
  interval?: number;
}
