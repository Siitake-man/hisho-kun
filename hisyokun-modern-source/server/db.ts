import { eq, and, gte, lte, desc, asc } from "drizzle-orm";
import { drizzle } from "drizzle-orm/mysql2";
import { 
  InsertUser, users, 
  events, InsertEvent, Event,
  categories, InsertCategory, Category,
  stickyNotes, InsertStickyNote, StickyNote,
  notifications, InsertNotification, Notification,
  googleCalendarSync, InsertGoogleCalendarSync, GoogleCalendarSync
} from "../drizzle/schema";
import { ENV } from './_core/env';

let _db: ReturnType<typeof drizzle> | null = null;

export async function getDb() {
  if (!_db && process.env.DATABASE_URL) {
    try {
      _db = drizzle(process.env.DATABASE_URL);
    } catch (error) {
      console.warn("[Database] Failed to connect:", error);
      _db = null;
    }
  }
  return _db;
}

// ============ User Queries ============
export async function upsertUser(user: InsertUser): Promise<void> {
  if (!user.openId) {
    throw new Error("User openId is required for upsert");
  }

  const db = await getDb();
  if (!db) {
    console.warn("[Database] Cannot upsert user: database not available");
    return;
  }

  try {
    const values: InsertUser = { openId: user.openId };
    const updateSet: Record<string, unknown> = {};

    const textFields = ["name", "email", "loginMethod"] as const;
    type TextField = (typeof textFields)[number];

    const assignNullable = (field: TextField) => {
      const value = user[field];
      if (value === undefined) return;
      const normalized = value ?? null;
      values[field] = normalized;
      updateSet[field] = normalized;
    };

    textFields.forEach(assignNullable);

    if (user.lastSignedIn !== undefined) {
      values.lastSignedIn = user.lastSignedIn;
      updateSet.lastSignedIn = user.lastSignedIn;
    }
    if (user.role !== undefined) {
      values.role = user.role;
      updateSet.role = user.role;
    } else if (user.openId === ENV.ownerOpenId) {
      values.role = 'admin';
      updateSet.role = 'admin';
    }

    if (!values.lastSignedIn) {
      values.lastSignedIn = new Date();
    }

    if (Object.keys(updateSet).length === 0) {
      updateSet.lastSignedIn = new Date();
    }

    await db.insert(users).values(values).onDuplicateKeyUpdate({ set: updateSet });
  } catch (error) {
    console.error("[Database] Failed to upsert user:", error);
    throw error;
  }
}

export async function getUserByOpenId(openId: string) {
  const db = await getDb();
  if (!db) return undefined;
  const result = await db.select().from(users).where(eq(users.openId, openId)).limit(1);
  return result.length > 0 ? result[0] : undefined;
}

// ============ Event Queries ============
export async function createEvent(event: InsertEvent): Promise<Event> {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  const result = await db.insert(events).values(event);
  const insertId = result[0].insertId;
  const created = await db.select().from(events).where(eq(events.id, insertId)).limit(1);
  return created[0];
}

export async function getEventById(id: number, userId: number): Promise<Event | undefined> {
  const db = await getDb();
  if (!db) return undefined;
  const result = await db.select().from(events)
    .where(and(eq(events.id, id), eq(events.userId, userId)))
    .limit(1);
  return result[0];
}

export async function getEventsByDateRange(
  userId: number, 
  startDate: number, 
  endDate: number
): Promise<Event[]> {
  const db = await getDb();
  if (!db) return [];
  
  return db.select().from(events)
    .where(and(
      eq(events.userId, userId),
      gte(events.startTime, startDate),
      lte(events.startTime, endDate)
    ))
    .orderBy(asc(events.startTime));
}

export async function getAllEvents(userId: number): Promise<Event[]> {
  const db = await getDb();
  if (!db) return [];
  return db.select().from(events)
    .where(eq(events.userId, userId))
    .orderBy(asc(events.startTime));
}

export async function updateEvent(id: number, userId: number, data: Partial<InsertEvent>): Promise<Event | undefined> {
  const db = await getDb();
  if (!db) return undefined;
  
  await db.update(events)
    .set({ ...data, updatedAt: new Date() })
    .where(and(eq(events.id, id), eq(events.userId, userId)));
  
  return getEventById(id, userId);
}

export async function deleteEvent(id: number, userId: number): Promise<boolean> {
  const db = await getDb();
  if (!db) return false;
  
  const result = await db.delete(events)
    .where(and(eq(events.id, id), eq(events.userId, userId)));
  return result[0].affectedRows > 0;
}

// ============ Category Queries ============
export async function createCategory(category: InsertCategory): Promise<Category> {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  const result = await db.insert(categories).values(category);
  const insertId = result[0].insertId;
  const created = await db.select().from(categories).where(eq(categories.id, insertId)).limit(1);
  return created[0];
}

export async function getCategoriesByUser(userId: number): Promise<Category[]> {
  const db = await getDb();
  if (!db) return [];
  return db.select().from(categories).where(eq(categories.userId, userId));
}

export async function updateCategory(id: number, userId: number, data: Partial<InsertCategory>): Promise<Category | undefined> {
  const db = await getDb();
  if (!db) return undefined;
  
  await db.update(categories)
    .set(data)
    .where(and(eq(categories.id, id), eq(categories.userId, userId)));
  
  const result = await db.select().from(categories)
    .where(and(eq(categories.id, id), eq(categories.userId, userId)))
    .limit(1);
  return result[0];
}

export async function deleteCategory(id: number, userId: number): Promise<boolean> {
  const db = await getDb();
  if (!db) return false;
  
  const result = await db.delete(categories)
    .where(and(eq(categories.id, id), eq(categories.userId, userId)));
  return result[0].affectedRows > 0;
}

// ============ Sticky Note Queries ============
export async function createStickyNote(note: InsertStickyNote): Promise<StickyNote> {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  const result = await db.insert(stickyNotes).values(note);
  const insertId = result[0].insertId;
  const created = await db.select().from(stickyNotes).where(eq(stickyNotes.id, insertId)).limit(1);
  return created[0];
}

export async function getStickyNoteById(id: number, userId: number): Promise<StickyNote | undefined> {
  const db = await getDb();
  if (!db) return undefined;
  const result = await db.select().from(stickyNotes)
    .where(and(eq(stickyNotes.id, id), eq(stickyNotes.userId, userId)))
    .limit(1);
  return result[0];
}

export async function getStickyNotesByUser(userId: number): Promise<StickyNote[]> {
  const db = await getDb();
  if (!db) return [];
  return db.select().from(stickyNotes)
    .where(eq(stickyNotes.userId, userId))
    .orderBy(desc(stickyNotes.zIndex));
}

export async function updateStickyNote(id: number, userId: number, data: Partial<InsertStickyNote>): Promise<StickyNote | undefined> {
  const db = await getDb();
  if (!db) return undefined;
  
  await db.update(stickyNotes)
    .set({ ...data, updatedAt: new Date() })
    .where(and(eq(stickyNotes.id, id), eq(stickyNotes.userId, userId)));
  
  const result = await db.select().from(stickyNotes)
    .where(and(eq(stickyNotes.id, id), eq(stickyNotes.userId, userId)))
    .limit(1);
  return result[0];
}

export async function deleteStickyNote(id: number, userId: number): Promise<boolean> {
  const db = await getDb();
  if (!db) return false;
  
  const result = await db.delete(stickyNotes)
    .where(and(eq(stickyNotes.id, id), eq(stickyNotes.userId, userId)));
  return result[0].affectedRows > 0;
}

// ============ Notification Queries ============
export async function createNotification(notification: InsertNotification): Promise<Notification> {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  const result = await db.insert(notifications).values(notification);
  const insertId = result[0].insertId;
  const created = await db.select().from(notifications).where(eq(notifications.id, insertId)).limit(1);
  return created[0];
}

export async function getNotificationsByEvent(eventId: number): Promise<Notification[]> {
  const db = await getDb();
  if (!db) return [];
  return db.select().from(notifications).where(eq(notifications.eventId, eventId));
}

export async function getPendingNotifications(userId: number): Promise<Notification[]> {
  const db = await getDb();
  if (!db) return [];
  return db.select().from(notifications)
    .where(and(
      eq(notifications.userId, userId),
      eq(notifications.isEnabled, true),
      eq(notifications.isSent, false)
    ));
}

export async function markNotificationSent(id: number): Promise<void> {
  const db = await getDb();
  if (!db) return;
  await db.update(notifications)
    .set({ isSent: true, sentAt: new Date() })
    .where(eq(notifications.id, id));
}

export async function deleteNotificationsByEvent(eventId: number): Promise<void> {
  const db = await getDb();
  if (!db) return;
  await db.delete(notifications).where(eq(notifications.eventId, eventId));
}

// ============ Google Calendar Sync Queries ============
export async function getGoogleCalendarSync(userId: number): Promise<GoogleCalendarSync | undefined> {
  const db = await getDb();
  if (!db) return undefined;
  const result = await db.select().from(googleCalendarSync)
    .where(eq(googleCalendarSync.userId, userId))
    .limit(1);
  return result[0];
}

export async function upsertGoogleCalendarSync(data: InsertGoogleCalendarSync): Promise<GoogleCalendarSync> {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  const existing = await getGoogleCalendarSync(data.userId);
  
  if (existing) {
    await db.update(googleCalendarSync)
      .set({ ...data, updatedAt: new Date() })
      .where(eq(googleCalendarSync.userId, data.userId));
    return (await getGoogleCalendarSync(data.userId))!;
  } else {
    const result = await db.insert(googleCalendarSync).values(data);
    const insertId = result[0].insertId;
    const created = await db.select().from(googleCalendarSync).where(eq(googleCalendarSync.id, insertId)).limit(1);
    return created[0];
  }
}

export async function deleteGoogleCalendarSync(userId: number): Promise<boolean> {
  const db = await getDb();
  if (!db) return false;
  
  const result = await db.delete(googleCalendarSync)
    .where(eq(googleCalendarSync.userId, userId));
  return result[0].affectedRows > 0;
}
