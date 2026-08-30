#include "ui_actions.h"

static UiActionHandler s_handler = nullptr;

void uiActionsSetHandler(UiActionHandler handler) { s_handler = handler; }

void uiActionsFire(UiActionId id, const UiActionCtx& ctx) {
  if (s_handler) s_handler(id, ctx);
}
