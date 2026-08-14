import { COOKIE_NAME } from "@shared/const";
import { getSessionCookieOptions } from "./_core/cookies";
import { systemRouter } from "./_core/systemRouter";
import { publicProcedure, protectedProcedure, router } from "./_core/trpc";
import { z } from "zod";
import * as db from "./db";
import { RecurrenceRule } from "../drizzle/schema";

// Zod schemas for validation
const recurrenceTypeSchema = z.enum([
  "once", "yearly_date", "yearly_weekday", "monthly_date", 
  "monthly_end", "monthly_weekday", "biweekly", "weekly", "daily"
]);

const recurrenceRuleSchema = z.object({
  month: z.number().min(1).max(12).optional(),
  day: z.number().min(1).max(31).optional(),
  weekNumber: z.number().min(-1).max(5).optional(),
  weekday: z.number().min(0).max(6).optional(),
  startDate: z.number().optional(),
  weekdays: z.array(z.number().min(0).max(6)).optional(),
  interval: z.number().min(1).optional(),
}).optional();

const createEventSchema = z.object({
  title: z.string().min(1).max(200),
  description: z.string().optional(),
  startTime: z.number(),
  endTime: z.number().optional(),
  isAllDay: z.boolean().default(false),
  recurrenceType: recurrenceTypeSchema.default("once"),
  recurrenceRule: recurrenceRuleSchema,
  recurrenceEndDate: z.number().optional(),
  categoryId: z.number().optional(),
  color: z.string().regex(/^#[0-9A-Fa-f]{6}$/).optional(),
});

const updateEventSchema = createEventSchema.partial().extend({
  id: z.number(),
});

const createCategorySchema = z.object({
  name: z.string().min(1).max(100),
  color: z.string().regex(/^#[0-9A-Fa-f]{6}$/).default("#D4A574"),
  icon: z.string().max(50).default("calendar"),
});

const updateCategorySchema = createCategorySchema.partial().extend({
  id: z.number(),
});

const createStickyNoteSchema = z.object({
  content: z.string().min(1),
  color: z.string().regex(/^#[0-9A-Fa-f]{6}$/).default("#FFFACD"),
  positionX: z.number().default(100),
  positionY: z.number().default(100),
  width: z.number().default(200),
  height: z.number().default(150),
});

const updateStickyNoteSchema = z.object({
  id: z.number(),
  content: z.string().optional(),
  color: z.string().regex(/^#[0-9A-Fa-f]{6}$/).optional(),
  positionX: z.number().optional(),
  positionY: z.number().optional(),
  width: z.number().optional(),
  height: z.number().optional(),
  zIndex: z.number().optional(),
  isMinimized: z.boolean().optional(),
});

const createNotificationSchema = z.object({
  eventId: z.number(),
  minutesBefore: z.number().min(0).max(43200), // Max 30 days in minutes
  isEnabled: z.boolean().default(true),
});

export const appRouter = router({
  system: systemRouter,
  
  auth: router({
    me: publicProcedure.query(opts => opts.ctx.user),
    logout: publicProcedure.mutation(({ ctx }) => {
      const cookieOptions = getSessionCookieOptions(ctx.req);
      ctx.res.clearCookie(COOKIE_NAME, { ...cookieOptions, maxAge: -1 });
      return { success: true } as const;
    }),
  }),

  // Events router
  events: router({
    list: protectedProcedure
      .input(z.object({
        startDate: z.number().optional(),
        endDate: z.number().optional(),
      }).optional())
      .query(async ({ ctx, input }) => {
        if (input?.startDate && input?.endDate) {
          return db.getEventsByDateRange(ctx.user.id, input.startDate, input.endDate);
        }
        return db.getAllEvents(ctx.user.id);
      }),

    get: protectedProcedure
      .input(z.object({ id: z.number() }))
      .query(async ({ ctx, input }) => {
        return db.getEventById(input.id, ctx.user.id);
      }),

    create: protectedProcedure
      .input(createEventSchema)
      .mutation(async ({ ctx, input }) => {
        return db.createEvent({
          ...input,
          userId: ctx.user.id,
          recurrenceRule: input.recurrenceRule as RecurrenceRule,
        });
      }),

    update: protectedProcedure
      .input(updateEventSchema)
      .mutation(async ({ ctx, input }) => {
        const { id, ...data } = input;
        return db.updateEvent(id, ctx.user.id, {
          ...data,
          recurrenceRule: data.recurrenceRule as RecurrenceRule,
        });
      }),

    delete: protectedProcedure
      .input(z.object({ id: z.number() }))
      .mutation(async ({ ctx, input }) => {
        // Delete associated notifications first
        await db.deleteNotificationsByEvent(input.id);
        return db.deleteEvent(input.id, ctx.user.id);
      }),

    // Get today's events for the widget
    today: protectedProcedure.query(async ({ ctx }) => {
      const now = new Date();
      const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
      const endOfDay = startOfDay + 24 * 60 * 60 * 1000 - 1;
      return db.getEventsByDateRange(ctx.user.id, startOfDay, endOfDay);
    }),

    // Get upcoming events (next 7 days)
    upcoming: protectedProcedure.query(async ({ ctx }) => {
      const now = Date.now();
      const weekLater = now + 7 * 24 * 60 * 60 * 1000;
      return db.getEventsByDateRange(ctx.user.id, now, weekLater);
    }),
  }),

  // Categories router
  categories: router({
    list: protectedProcedure.query(async ({ ctx }) => {
      return db.getCategoriesByUser(ctx.user.id);
    }),

    create: protectedProcedure
      .input(createCategorySchema)
      .mutation(async ({ ctx, input }) => {
        return db.createCategory({
          ...input,
          userId: ctx.user.id,
        });
      }),

    update: protectedProcedure
      .input(updateCategorySchema)
      .mutation(async ({ ctx, input }) => {
        const { id, ...data } = input;
        return db.updateCategory(id, ctx.user.id, data);
      }),

    delete: protectedProcedure
      .input(z.object({ id: z.number() }))
      .mutation(async ({ ctx, input }) => {
        return db.deleteCategory(input.id, ctx.user.id);
      }),
  }),

  // Sticky Notes router
  stickyNotes: router({
    list: protectedProcedure.query(async ({ ctx }) => {
      return db.getStickyNotesByUser(ctx.user.id);
    }),

    get: protectedProcedure
      .input(z.object({ id: z.number() }))
      .query(async ({ ctx, input }) => {
        return db.getStickyNoteById(input.id, ctx.user.id);
      }),

    create: protectedProcedure
      .input(createStickyNoteSchema)
      .mutation(async ({ ctx, input }) => {
        return db.createStickyNote({
          ...input,
          userId: ctx.user.id,
        });
      }),

    update: protectedProcedure
      .input(updateStickyNoteSchema)
      .mutation(async ({ ctx, input }) => {
        const { id, ...data } = input;
        return db.updateStickyNote(id, ctx.user.id, data);
      }),

    delete: protectedProcedure
      .input(z.object({ id: z.number() }))
      .mutation(async ({ ctx, input }) => {
        return db.deleteStickyNote(input.id, ctx.user.id);
      }),
  }),

  // Notifications router
  notifications: router({
    listByEvent: protectedProcedure
      .input(z.object({ eventId: z.number() }))
      .query(async ({ input }) => {
        return db.getNotificationsByEvent(input.eventId);
      }),

    pending: protectedProcedure.query(async ({ ctx }) => {
      return db.getPendingNotifications(ctx.user.id);
    }),

    create: protectedProcedure
      .input(createNotificationSchema)
      .mutation(async ({ ctx, input }) => {
        return db.createNotification({
          ...input,
          userId: ctx.user.id,
        });
      }),

    markSent: protectedProcedure
      .input(z.object({ id: z.number() }))
      .mutation(async ({ input }) => {
        await db.markNotificationSent(input.id);
        return { success: true };
      }),
  }),

  // Google Calendar Sync router (placeholder for future implementation)
  googleCalendar: router({
    getStatus: protectedProcedure.query(async ({ ctx }) => {
      const sync = await db.getGoogleCalendarSync(ctx.user.id);
      return {
        isConnected: !!sync?.accessToken,
        syncEnabled: sync?.syncEnabled ?? false,
        lastSyncAt: sync?.lastSyncAt,
        calendarIds: sync?.calendarIds as string[] | null,
      };
    }),

    disconnect: protectedProcedure.mutation(async ({ ctx }) => {
      return db.deleteGoogleCalendarSync(ctx.user.id);
    }),
  }),
});

export type AppRouter = typeof appRouter;
