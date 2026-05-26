import { __rest } from "tslib";
import { jsx as _jsx } from "react/jsx-runtime";
import { createContext, useRef } from 'react';
import styles from '@patternfly/react-styles/css/components/Drawer/drawer.mjs';
import { css } from '@patternfly/react-styles';
export var DrawerColorVariant;
(function (DrawerColorVariant) {
    DrawerColorVariant["default"] = "default";
    DrawerColorVariant["secondary"] = "secondary";
    /**
     * @deprecated `DrawerColorVariant.noBackground` is deprecated. Use the `isPlain` prop on `DrawerPanelContent` and the `DrawerSection`instead.
     */
    DrawerColorVariant["noBackground"] = "no-background";
})(DrawerColorVariant || (DrawerColorVariant = {}));
export const DrawerContext = createContext({
    isExpanded: false,
    isStatic: false,
    onExpand: () => { },
    position: 'end',
    drawerRef: null,
    drawerContentRef: null,
    isInline: false
});
export const Drawer = (_a) => {
    var { className = '', children, isExpanded = false, isInline = false, isPill = false, isStatic = false, position = 'end', onExpand = () => { } } = _a, props = __rest(_a, ["className", "children", "isExpanded", "isInline", "isPill", "isStatic", "position", "onExpand"]);
    const drawerRef = useRef(undefined);
    const drawerContentRef = useRef(undefined);
    return (_jsx(DrawerContext.Provider, { value: { isExpanded, isStatic, onExpand, position, drawerRef, drawerContentRef, isInline }, children: _jsx("div", Object.assign({ className: css(styles.drawer, isExpanded && styles.modifiers.expanded, isInline && styles.modifiers.inline, isPill && styles.modifiers.pill, isStatic && styles.modifiers.static, (position === 'left' || position === 'start') && styles.modifiers.panelLeft, position === 'bottom' && styles.modifiers.panelBottom, className), ref: drawerRef }, props, { children: children })) }));
};
Drawer.displayName = 'Drawer';
//# sourceMappingURL=Drawer.js.map