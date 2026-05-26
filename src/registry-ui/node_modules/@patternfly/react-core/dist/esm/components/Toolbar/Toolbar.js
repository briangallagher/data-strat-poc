import { __rest } from "tslib";
import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Component, createRef } from 'react';
import styles from '@patternfly/react-styles/css/components/Toolbar/toolbar.mjs';
import { css } from '@patternfly/react-styles';
import { ToolbarContext } from './ToolbarUtils';
import { ToolbarLabelGroupContent } from './ToolbarLabelGroupContent';
import { formatBreakpointMods, canUseDOM } from '../../helpers/util';
import { getOUIAProps } from '../../helpers';
import { SSRSafeIds } from '../../helpers/SSRSafeIds/SSRSafeIds';
import { PageContext } from '../Page/PageContext';
export var ToolbarColorVariant;
(function (ToolbarColorVariant) {
    ToolbarColorVariant["default"] = "default";
    ToolbarColorVariant["primary"] = "primary";
    ToolbarColorVariant["secondary"] = "secondary";
    ToolbarColorVariant["noBackground"] = "no-background";
})(ToolbarColorVariant || (ToolbarColorVariant = {}));
class Toolbar extends Component {
    constructor() {
        super(...arguments);
        this.labelGroupContentRef = createRef();
        this.staticFilterInfo = {};
        this.hasNoPadding = false;
        this.state = {
            isManagedToggleExpanded: false,
            filterInfo: {},
            windowWidth: 1200
        };
        this.isToggleManaged = () => !(this.props.isExpanded || !!this.props.toggleIsExpanded);
        this.toggleIsExpanded = () => {
            this.setState((prevState) => ({
                isManagedToggleExpanded: !prevState.isManagedToggleExpanded
            }));
        };
        this.closeExpandableContent = (e) => {
            if (e.target.innerWidth !== this.state.windowWidth) {
                this.setState(() => ({
                    isManagedToggleExpanded: false,
                    windowWidth: e.target.innerWidth
                }));
            }
        };
        this.updateNumberFilters = (categoryName, numberOfFilters) => {
            const filterInfoToUpdate = Object.assign({}, this.staticFilterInfo);
            if (!filterInfoToUpdate.hasOwnProperty(categoryName) || filterInfoToUpdate[categoryName] !== numberOfFilters) {
                filterInfoToUpdate[categoryName] = numberOfFilters;
                this.staticFilterInfo = filterInfoToUpdate;
                this.setState({ filterInfo: filterInfoToUpdate });
            }
        };
        this.getNumberOfFilters = () => Object.values(this.state.filterInfo).reduce((acc, cur) => acc + cur, 0);
        this.renderToolbar = (randomId, generatedOuiaId) => {
            const _a = this.props, { hasNoPadding, clearAllFilters, clearFiltersButtonText, collapseListedFiltersBreakpoint, isExpanded: isExpandedProp, toggleIsExpanded, className, children, isFullHeight, isStatic, isStickyBase, isStickyStuck, inset, isSticky, isVertical, ouiaId, numberOfFiltersText, customLabelGroupContent, colorVariant = ToolbarColorVariant.default } = _a, props = __rest(_a, ["hasNoPadding", "clearAllFilters", "clearFiltersButtonText", "collapseListedFiltersBreakpoint", "isExpanded", "toggleIsExpanded", "className", "children", "isFullHeight", "isStatic", "isStickyBase", "isStickyStuck", "inset", "isSticky", "isVertical", "ouiaId", "numberOfFiltersText", "customLabelGroupContent", "colorVariant"]);
            const { isManagedToggleExpanded } = this.state;
            const isToggleManaged = this.isToggleManaged();
            const isExpanded = isToggleManaged ? isManagedToggleExpanded : isExpandedProp;
            const numberOfFilters = this.getNumberOfFilters();
            const showClearFiltersButton = numberOfFilters > 0;
            return (_jsx(PageContext.Consumer, { children: ({ width, getBreakpoint }) => (_jsx("div", Object.assign({ className: css(styles.toolbar, hasNoPadding && styles.modifiers.noPadding, isFullHeight && styles.modifiers.fullHeight, isStatic && styles.modifiers.static, isSticky && styles.modifiers.sticky, isStickyBase && styles.modifiers.stickyBase, isStickyStuck && styles.modifiers.stickyStuck, isVertical && styles.modifiers.vertical, formatBreakpointMods(inset, styles, '', getBreakpoint(width)), colorVariant === 'primary' && styles.modifiers.primary, colorVariant === 'secondary' && styles.modifiers.secondary, colorVariant === 'no-background' && styles.modifiers.noBackground, className), id: randomId }, getOUIAProps(Toolbar.displayName, ouiaId !== undefined ? ouiaId : generatedOuiaId), props, { children: _jsxs(ToolbarContext.Provider, { value: {
                            isExpanded,
                            toggleIsExpanded: isToggleManaged ? this.toggleIsExpanded : toggleIsExpanded,
                            labelGroupContentRef: this.labelGroupContentRef,
                            updateNumberFilters: this.updateNumberFilters,
                            numberOfFilters,
                            clearAllFilters,
                            clearFiltersButtonText,
                            showClearFiltersButton,
                            toolbarId: randomId,
                            customLabelGroupContent
                        }, children: [children, _jsx(ToolbarLabelGroupContent, { isExpanded: isExpanded, labelGroupContentRef: this.labelGroupContentRef, clearAllFilters: clearAllFilters, showClearFiltersButton: showClearFiltersButton, clearFiltersButtonText: clearFiltersButtonText, numberOfFilters: numberOfFilters, numberOfFiltersText: numberOfFiltersText, collapseListedFiltersBreakpoint: collapseListedFiltersBreakpoint, customLabelGroupContent: customLabelGroupContent })] }) }))) }));
        };
    }
    componentDidMount() {
        if (canUseDOM) {
            this.setState({ windowWidth: window.innerWidth });
        }
        if (this.isToggleManaged() && canUseDOM) {
            window.addEventListener('resize', this.closeExpandableContent);
        }
    }
    componentWillUnmount() {
        if (this.isToggleManaged() && canUseDOM) {
            window.removeEventListener('resize', this.closeExpandableContent);
        }
    }
    render() {
        return (_jsx(SSRSafeIds, { prefix: "pf-random-id-", ouiaComponentType: "Toolbar", children: (generatedId, generatedOuiaId) => this.renderToolbar(this.props.id || generatedId, generatedOuiaId) }));
    }
}
Toolbar.displayName = 'Toolbar';
export { Toolbar };
//# sourceMappingURL=Toolbar.js.map