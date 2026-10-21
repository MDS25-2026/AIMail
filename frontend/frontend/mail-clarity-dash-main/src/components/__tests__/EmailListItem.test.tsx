// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { emailFixture } from "../../test/emailFixture";
import { renderWithProviders } from "../../test/render";
import EmailListItem from "../EmailListItem";

const { t } = createI18n(Language.English);

const row = (isAnswered: boolean, isRead = true) =>
  renderWithProviders(
    <ul>
      <EmailListItem
        email={emailFixture({ isAnswered, isRead: true })}
        isRead={isRead}
        selected={false}
        onSelect={() => undefined}
      />
    </ul>,
  );

test("an answered conversation says you replied", () => {
  row(true);
  expect(screen.getByText(t("inbox.youReplied"))).toBeTruthy();
});

test("one still waiting on you says nothing about replying", () => {
  row(false);
  expect(screen.queryByText(t("inbox.youReplied"))).toBeNull();
});

test("the conversation's unread state shows, even when its newest email was read", () => {
  row(false, false);
  expect(screen.getByText(t("inbox.unread"), { exact: false })).toBeTruthy();
});
