import { describe, expect, it, vi, beforeEach } from "vitest";
import { appRouter } from "./routers";
import type { TrpcContext } from "./_core/context";

// Mock the database functions
vi.mock("./db", () => ({
  createEvent: vi.fn(),
  getEventById: vi.fn(),
  getEventsByDateRange: vi.fn(),
  getAllEvents: vi.fn(),
  updateEvent: vi.fn(),
  deleteEvent: vi.fn(),
  deleteNotificationsByEvent: vi.fn(),
}));

import * as db from "./db";

type AuthenticatedUser = NonNullable<TrpcContext["user"]>;

function createAuthContext(): TrpcContext {
  const user: AuthenticatedUser = {
    id: 1,
    openId: "test-user",
    email: "test@example.com",
    name: "Test User",
    loginMethod: "manus",
    role: "user",
    createdAt: new Date(),
    updatedAt: new Date(),
    lastSignedIn: new Date(),
  };

  return {
    user,
    req: {
      protocol: "https",
      headers: {},
    } as TrpcContext["req"],
    res: {
      clearCookie: vi.fn(),
    } as unknown as TrpcContext["res"],
  };
}

describe("events router", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("events.create", () => {
    it("creates an event with required fields", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      const mockEvent = {
        id: 1,
        userId: 1,
        title: "Test Event",
        description: null,
        startTime: Date.now(),
        endTime: null,
        isAllDay: false,
        recurrenceType: "once" as const,
        recurrenceRule: null,
        recurrenceEndDate: null,
        categoryId: null,
        color: "#D4A574",
        googleEventId: null,
        googleCalendarId: null,
        lastSyncedAt: null,
        createdAt: new Date(),
        updatedAt: new Date(),
      };

      vi.mocked(db.createEvent).mockResolvedValue(mockEvent);

      const result = await caller.events.create({
        title: "Test Event",
        startTime: mockEvent.startTime,
        color: "#D4A574",
      });

      expect(db.createEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Test Event",
          userId: 1,
        })
      );
      expect(result).toEqual(mockEvent);
    });

    it("creates an all-day event", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      const startTime = new Date("2026-01-24").getTime();
      const mockEvent = {
        id: 2,
        userId: 1,
        title: "All Day Event",
        description: "A full day event",
        startTime,
        endTime: startTime + 86400000 - 1,
        isAllDay: true,
        recurrenceType: "once" as const,
        recurrenceRule: null,
        recurrenceEndDate: null,
        categoryId: null,
        color: "#E57373",
        googleEventId: null,
        googleCalendarId: null,
        lastSyncedAt: null,
        createdAt: new Date(),
        updatedAt: new Date(),
      };

      vi.mocked(db.createEvent).mockResolvedValue(mockEvent);

      const result = await caller.events.create({
        title: "All Day Event",
        description: "A full day event",
        startTime,
        endTime: startTime + 86400000 - 1,
        isAllDay: true,
        color: "#E57373",
      });

      expect(db.createEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "All Day Event",
          isAllDay: true,
        })
      );
      expect(result.isAllDay).toBe(true);
    });

    it("creates a recurring event", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      const startTime = Date.now();
      const mockEvent = {
        id: 3,
        userId: 1,
        title: "Weekly Meeting",
        description: null,
        startTime,
        endTime: startTime + 3600000,
        isAllDay: false,
        recurrenceType: "weekly" as const,
        recurrenceRule: { weekdays: [1, 3, 5] },
        recurrenceEndDate: null,
        categoryId: null,
        color: "#64B5F6",
        googleEventId: null,
        googleCalendarId: null,
        lastSyncedAt: null,
        createdAt: new Date(),
        updatedAt: new Date(),
      };

      vi.mocked(db.createEvent).mockResolvedValue(mockEvent);

      const result = await caller.events.create({
        title: "Weekly Meeting",
        startTime,
        endTime: startTime + 3600000,
        recurrenceType: "weekly",
        recurrenceRule: { weekdays: [1, 3, 5] },
        color: "#64B5F6",
      });

      expect(db.createEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          recurrenceType: "weekly",
          recurrenceRule: { weekdays: [1, 3, 5] },
        })
      );
      expect(result.recurrenceType).toBe("weekly");
    });
  });

  describe("events.list", () => {
    it("returns all events when no date range specified", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      const mockEvents = [
        { id: 1, title: "Event 1", userId: 1, startTime: Date.now() },
        { id: 2, title: "Event 2", userId: 1, startTime: Date.now() + 86400000 },
      ];

      vi.mocked(db.getAllEvents).mockResolvedValue(mockEvents as any);

      const result = await caller.events.list();

      expect(db.getAllEvents).toHaveBeenCalledWith(1);
      expect(result).toHaveLength(2);
    });

    it("returns events within date range", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      const startDate = new Date("2026-01-01").getTime();
      const endDate = new Date("2026-01-31").getTime();
      const mockEvents = [
        { id: 1, title: "January Event", userId: 1, startTime: startDate + 86400000 },
      ];

      vi.mocked(db.getEventsByDateRange).mockResolvedValue(mockEvents as any);

      const result = await caller.events.list({ startDate, endDate });

      expect(db.getEventsByDateRange).toHaveBeenCalledWith(1, startDate, endDate);
      expect(result).toHaveLength(1);
    });
  });

  describe("events.get", () => {
    it("returns a specific event by id", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      const mockEvent = {
        id: 1,
        userId: 1,
        title: "Test Event",
        startTime: Date.now(),
      };

      vi.mocked(db.getEventById).mockResolvedValue(mockEvent as any);

      const result = await caller.events.get({ id: 1 });

      expect(db.getEventById).toHaveBeenCalledWith(1, 1);
      expect(result).toEqual(mockEvent);
    });
  });

  describe("events.update", () => {
    it("updates an event", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      const mockUpdatedEvent = {
        id: 1,
        userId: 1,
        title: "Updated Event",
        startTime: Date.now(),
      };

      vi.mocked(db.updateEvent).mockResolvedValue(mockUpdatedEvent as any);

      const result = await caller.events.update({
        id: 1,
        title: "Updated Event",
      });

      expect(db.updateEvent).toHaveBeenCalledWith(
        1,
        1,
        expect.objectContaining({ title: "Updated Event" })
      );
      expect(result?.title).toBe("Updated Event");
    });
  });

  describe("events.delete", () => {
    it("deletes an event and its notifications", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      vi.mocked(db.deleteNotificationsByEvent).mockResolvedValue(undefined);
      vi.mocked(db.deleteEvent).mockResolvedValue(true);

      const result = await caller.events.delete({ id: 1 });

      expect(db.deleteNotificationsByEvent).toHaveBeenCalledWith(1);
      expect(db.deleteEvent).toHaveBeenCalledWith(1, 1);
      expect(result).toBe(true);
    });
  });

  describe("events.today", () => {
    it("returns today's events", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      const mockEvents = [
        { id: 1, title: "Today's Event", userId: 1, startTime: Date.now() },
      ];

      vi.mocked(db.getEventsByDateRange).mockResolvedValue(mockEvents as any);

      const result = await caller.events.today();

      expect(db.getEventsByDateRange).toHaveBeenCalled();
      expect(result).toHaveLength(1);
    });
  });
});
