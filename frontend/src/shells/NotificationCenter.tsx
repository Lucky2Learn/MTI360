"use client";

import { useId, useRef, useState } from "react";

import {
  Button,
  EmptyState,
  IconButton,
  Popover,
} from "@/design-system/components";
import { NotificationIcon } from "@/design-system/icons";
import { cx, focusRing } from "@/design-system/lib/cx";

// NotificationCenter (T00-08): in-app notification surface built on the
// T00-07C Popover (focus moves in, Escape closes, focus returns to the bell).
// UI foundation only: the list comes from props (static demo data today);
// there is no notification backend, polling, WebSocket or push, and read state
// lives in this component until a later phase persists it. Unread items are
// marked by a dot, heavier weight and an "Unread" prefix for screen readers —
// never colour alone — and the bell's accessible name includes the count.

export type ShellNotification = {
  id: string;
  title: string;
  description?: string;
  /** Machine-readable time (ISO 8601). */
  timestamp: string;
  /** Human-readable time, e.g. "10 min ago". */
  timeLabel: string;
  read: boolean;
};

export type NotificationCenterProps = {
  notifications: ShellNotification[];
};

export function NotificationCenter({
  notifications: initial,
}: NotificationCenterProps) {
  const [notifications, setNotifications] = useState(initial);
  const listRef = useRef<HTMLUListElement>(null);
  const unread = notifications.filter((item) => !item.read).length;

  const markRead = (id?: string) =>
    setNotifications((items) =>
      items.map((item) =>
        id === undefined || item.id === id ? { ...item, read: true } : item,
      ),
    );

  return (
    <span className="relative flex">
      <Popover
        title="Notifications"
        placement="bottom end"
        trigger={
          <IconButton
            label={
              unread > 0 ? `Notifications, ${unread} unread` : "Notifications"
            }
            icon={NotificationIcon}
          />
        }
      >
        {notifications.length === 0 ? (
          <EmptyState
            title="No notifications"
            description="Updates about your work will appear here."
            titleAs="h3"
          />
        ) : (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-2">
              <p>{unread > 0 ? `${unread} unread` : "All caught up"}</p>
              <Button
                variant="tertiary"
                size="sm"
                isDisabled={unread === 0}
                onPress={() => {
                  markRead();
                  // The button disables itself; keep focus inside the panel.
                  listRef.current?.querySelector("button")?.focus();
                }}
              >
                Mark all as read
              </Button>
            </div>
            <ul
              ref={listRef}
              className="-mx-2 flex max-h-80 flex-col gap-1 overflow-y-auto"
            >
              {notifications.map((item) => (
                <NotificationRow
                  key={item.id}
                  item={item}
                  onMarkRead={() => markRead(item.id)}
                />
              ))}
            </ul>
          </div>
        )}
      </Popover>
      {unread > 0 && (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute top-1 right-1 flex min-w-5 items-center justify-center rounded-full bg-brand-primary px-1 text-caption-sm font-semibold text-text-inverse"
        >
          {unread}
        </span>
      )}
    </span>
  );
}

function NotificationRow({
  item,
  onMarkRead,
}: {
  item: ShellNotification;
  onMarkRead: () => void;
}) {
  const detailsId = useId();
  return (
    <li className="relative flex items-start gap-3 rounded-md p-2 transition-colors hover:bg-surface-hover motion-reduce:transition-none">
      <span
        aria-hidden="true"
        className={cx(
          "mt-2 size-2 shrink-0 rounded-full",
          item.read ? "bg-transparent" : "bg-accent-maritime",
        )}
      />
      <div className="flex min-w-0 flex-col gap-1">
        {/* The whole row is clickable (::after); the button carries the name. */}
        <button
          type="button"
          aria-describedby={detailsId}
          onClick={onMarkRead}
          className={cx(
            "cursor-pointer rounded-xs text-left text-text-primary after:absolute after:inset-0 after:rounded-md",
            !item.read && "font-semibold",
            focusRing,
          )}
        >
          {!item.read && <span className="sr-only">Unread: </span>}
          {item.title}
        </button>
        <p id={detailsId} className="flex flex-col gap-1">
          {item.description && <span>{item.description}</span>}
          <time
            dateTime={item.timestamp}
            className="text-caption text-text-muted"
          >
            {item.timeLabel}
          </time>
        </p>
      </div>
    </li>
  );
}
