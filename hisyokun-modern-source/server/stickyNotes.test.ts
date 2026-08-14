import { describe, expect, it, vi, beforeEach } from "vitest";
import { appRouter } from "./routers";
import type { TrpcContext } from "./_core/context";

// Mock the database functions
vi.mock("./db", () => ({
  createStickyNote: vi.fn(),
  getStickyNoteById: vi.fn(),
  getStickyNotesByUser: vi.fn(),
  updateStickyNote: vi.fn(),
  deleteStickyNote: vi.fn(),
  // Also mock event functions to prevent import errors
  createEvent: vi.fn(),
  getEventById: vi.fn(),
  getEventsByDateRange: vi.fn(),
  getAllEvents: vi.fn(),
  updateEvent: vi.fn(),
  deleteEvent: vi.fn(),
  deleteNotificationsByEvent: vi.fn(),
  createCategory: vi.fn(),
  getCategoriesByUser: vi.fn(),
  updateCategory: vi.fn(),
  deleteCategory: vi.fn(),
  createNotification: vi.fn(),
  getNotificationsByUser: vi.fn(),
  updateNotification: vi.fn(),
  deleteNotification: vi.fn(),
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

describe("stickyNotes router", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("stickyNotes.create", () => {
    it("creates a sticky note with content and color", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      const mockNote = {
        id: 1,
        userId: 1,
        content: "Test note content",
        color: "#FFFACD",
        positionX: 100,
        positionY: 100,
        width: 200,
        height: 150,
        zIndex: 1,
        isMinimized: false,
        createdAt: new Date(),
        updatedAt: new Date(),
      };

      vi.mocked(db.createStickyNote).mockResolvedValue(mockNote);

      const result = await caller.stickyNotes.create({
        content: "Test note content",
        color: "#FFFACD",
        positionX: 100,
        positionY: 100,
      });

      expect(db.createStickyNote).toHaveBeenCalledWith(
        expect.objectContaining({
          content: "Test note content",
          color: "#FFFACD",
          userId: 1,
        })
      );
      expect(result).toEqual(mockNote);
    });

    it("creates a sticky note with default position", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      const mockNote = {
        id: 2,
        userId: 1,
        content: "Another note",
        color: "#FFB6C1",
        positionX: null,
        positionY: null,
        width: null,
        height: null,
        zIndex: 1,
        isMinimized: false,
        createdAt: new Date(),
        updatedAt: new Date(),
      };

      vi.mocked(db.createStickyNote).mockResolvedValue(mockNote);

      const result = await caller.stickyNotes.create({
        content: "Another note",
        color: "#FFB6C1",
      });

      expect(db.createStickyNote).toHaveBeenCalled();
      expect(result.content).toBe("Another note");
    });
  });

  describe("stickyNotes.list", () => {
    it("returns all sticky notes for user", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      const mockNotes = [
        { id: 1, userId: 1, content: "Note 1", color: "#FFFACD" },
        { id: 2, userId: 1, content: "Note 2", color: "#FFB6C1" },
        { id: 3, userId: 1, content: "Note 3", color: "#ADD8E6" },
      ];

      vi.mocked(db.getStickyNotesByUser).mockResolvedValue(mockNotes as any);

      const result = await caller.stickyNotes.list();

      expect(db.getStickyNotesByUser).toHaveBeenCalledWith(1);
      expect(result).toHaveLength(3);
    });

    it("returns empty array when no notes exist", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      vi.mocked(db.getStickyNotesByUser).mockResolvedValue([]);

      const result = await caller.stickyNotes.list();

      expect(result).toHaveLength(0);
    });
  });

  describe("stickyNotes.get", () => {
    it("returns a specific sticky note by id", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      const mockNote = {
        id: 1,
        userId: 1,
        content: "Test note",
        color: "#FFFACD",
      };

      vi.mocked(db.getStickyNoteById).mockResolvedValue(mockNote as any);

      const result = await caller.stickyNotes.get({ id: 1 });

      expect(db.getStickyNoteById).toHaveBeenCalledWith(1, 1);
      expect(result).toEqual(mockNote);
    });
  });

  describe("stickyNotes.update", () => {
    it("updates sticky note content", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      const mockUpdatedNote = {
        id: 1,
        userId: 1,
        content: "Updated content",
        color: "#FFFACD",
      };

      vi.mocked(db.updateStickyNote).mockResolvedValue(mockUpdatedNote as any);

      const result = await caller.stickyNotes.update({
        id: 1,
        content: "Updated content",
      });

      expect(db.updateStickyNote).toHaveBeenCalledWith(
        1,
        1,
        expect.objectContaining({ content: "Updated content" })
      );
      expect(result?.content).toBe("Updated content");
    });

    it("updates sticky note position", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      const mockUpdatedNote = {
        id: 1,
        userId: 1,
        content: "Note",
        positionX: 200,
        positionY: 300,
      };

      vi.mocked(db.updateStickyNote).mockResolvedValue(mockUpdatedNote as any);

      const result = await caller.stickyNotes.update({
        id: 1,
        positionX: 200,
        positionY: 300,
      });

      expect(db.updateStickyNote).toHaveBeenCalledWith(
        1,
        1,
        expect.objectContaining({ positionX: 200, positionY: 300 })
      );
      expect(result?.positionX).toBe(200);
      expect(result?.positionY).toBe(300);
    });

    it("updates sticky note minimized state", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      const mockUpdatedNote = {
        id: 1,
        userId: 1,
        content: "Note",
        isMinimized: true,
      };

      vi.mocked(db.updateStickyNote).mockResolvedValue(mockUpdatedNote as any);

      const result = await caller.stickyNotes.update({
        id: 1,
        isMinimized: true,
      });

      expect(db.updateStickyNote).toHaveBeenCalledWith(
        1,
        1,
        expect.objectContaining({ isMinimized: true })
      );
      expect(result?.isMinimized).toBe(true);
    });

    it("updates sticky note zIndex", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      const mockUpdatedNote = {
        id: 1,
        userId: 1,
        content: "Note",
        zIndex: 10,
      };

      vi.mocked(db.updateStickyNote).mockResolvedValue(mockUpdatedNote as any);

      const result = await caller.stickyNotes.update({
        id: 1,
        zIndex: 10,
      });

      expect(db.updateStickyNote).toHaveBeenCalledWith(
        1,
        1,
        expect.objectContaining({ zIndex: 10 })
      );
      expect(result?.zIndex).toBe(10);
    });
  });

  describe("stickyNotes.delete", () => {
    it("deletes a sticky note", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      vi.mocked(db.deleteStickyNote).mockResolvedValue(true);

      const result = await caller.stickyNotes.delete({ id: 1 });

      expect(db.deleteStickyNote).toHaveBeenCalledWith(1, 1);
      expect(result).toBe(true);
    });

    it("returns false when note not found", async () => {
      const ctx = createAuthContext();
      const caller = appRouter.createCaller(ctx);
      
      vi.mocked(db.deleteStickyNote).mockResolvedValue(false);

      const result = await caller.stickyNotes.delete({ id: 999 });

      expect(db.deleteStickyNote).toHaveBeenCalledWith(999, 1);
      expect(result).toBe(false);
    });
  });
});
