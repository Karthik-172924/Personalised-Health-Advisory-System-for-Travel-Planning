(function () {
    "use strict";

    function qs(selector, scope) {
        return (scope || document).querySelector(selector);
    }

    function qsa(selector, scope) {
        return Array.prototype.slice.call((scope || document).querySelectorAll(selector));
    }

    function parseJson(value, fallback) {
        try {
            return JSON.parse(value);
        } catch (error) {
            return fallback;
        }
    }

    function initHeader() {
        var header = qs("#site-header");
        if (!header) {
            return;
        }

        function handleScroll() {
            header.classList.toggle("scrolled", window.scrollY > 12);
        }

        window.addEventListener("scroll", handleScroll, { passive: true });
        handleScroll();
    }

    function initChoiceChips() {
        qsa(".choice-row").forEach(function (row) {
            function refresh() {
                qsa(".choice-chip", row).forEach(function (chip) {
                    var input = qs("input", chip);
                    chip.classList.toggle("is-selected", Boolean(input && input.checked));
                });
            }

            row.addEventListener("change", refresh);
            refresh();
        });
    }

    function initAssessmentForm() {
        var form = qs("#health-form");
        if (!form) {
            return;
        }

        var storageKey = "travel_health_assessment";
        var fields = qsa("input, select, textarea", form);

        function fieldGroup(element) {
            return element.closest(".field-group") || element.parentElement;
        }

        function showError(element, message) {
            var group = fieldGroup(element);
            var error = qs(".field-error", group);
            if (!error) {
                error = document.createElement("p");
                error.className = "field-error";
                group.appendChild(error);
            }
            error.textContent = message;
            element.classList.add("input-error");
        }

        function clearError(element) {
            var group = fieldGroup(element);
            var error = qs(".field-error", group);
            if (error) {
                error.remove();
            }
            element.classList.remove("input-error");
        }

        function saveForm() {
            var payload = {};
            fields.forEach(function (field) {
                if (!field.name) {
                    return;
                }
                if ((field.type === "radio" || field.type === "checkbox") && !field.checked) {
                    return;
                }
                payload[field.name] = field.value;
            });
            localStorage.setItem(storageKey, JSON.stringify(payload));
        }

        function restoreForm() {
            var saved = parseJson(localStorage.getItem(storageKey), null);
            if (!saved) {
                return;
            }

            fields.forEach(function (field) {
                if (!field.name || !(field.name in saved)) {
                    return;
                }
                if (field.type === "radio") {
                    field.checked = saved[field.name] === field.value;
                } else {
                    field.value = saved[field.name];
                }
            });
        }

        function validateForm() {
            var valid = true;
            var age = qs("#age");
            var height = qs("#height");
            var weight = qs("#weight");
            var bpm = qs("#bmi");
            var bp = qs("#bp");
            var destination = qs("#destination");
            var month = qs("#travel_month");
            var year = qs("#travel_year");

            if (age) {
                if (!age.value || Number(age.value) < 1 || Number(age.value) > 120) {
                    showError(age, "Age must be between 1 and 120.");
                    valid = false;
                } else {
                    clearError(age);
                }
            }

            if (height) {
                if (!height.value || Number(height.value) < 50 || Number(height.value) > 250) {
                    showError(height, "Height must be between 50 and 250 cm.");
                    valid = false;
                } else {
                    clearError(height);
                }
            }

            if (weight) {
                if (!weight.value || Number(weight.value) < 20 || Number(weight.value) > 200) {
                    showError(weight, "Weight must be between 20 and 200 kg.");
                    valid = false;
                } else {
                    clearError(weight);
                }
            }

            if (bp) {
                if (!/^\d{2,3}\/\d{2,3}$/.test((bp.value || "").trim())) {
                    showError(bp, "Blood pressure must use the format 120/80.");
                    valid = false;
                } else {
                    clearError(bp);
                }
            }

            if (destination) {
                if (!(destination.value || "").trim()) {
                    showError(destination, "Destination is required.");
                    valid = false;
                } else {
                    clearError(destination);
                }
            }

            if (month && year) {
                var hasMonth = Boolean(month.value);
                var hasYear = Boolean(year.value);
                if (hasMonth !== hasYear) {
                    valid = false;
                    if (!hasMonth) {
                        showError(month, "Select a month or leave both date fields blank.");
                    } else {
                        clearError(month);
                    }
                    if (!hasYear) {
                        showError(year, "Select a year or leave both date fields blank.");
                    } else {
                        clearError(year);
                    }
                } else {
                    clearError(month);
                    clearError(year);
                }
            }

            return valid;
        }

        restoreForm();
        initChoiceChips();

        function updateCalculatedBmi() {
            var heightValue = Number(qs("#height")?.value);
            var weightValue = Number(qs("#weight")?.value);
            var bmiField = qs("#bmi");

            if (!bmiField) {
                return;
            }

            if (heightValue > 0 && weightValue > 0) {
                var bmiValue = weightValue / ((heightValue / 100) * (heightValue / 100));
                bmiField.value = bmiValue.toFixed(1);
            }
        }

        fields.forEach(function (field) {
            field.addEventListener("input", function () {
                saveForm();
                updateCalculatedBmi();
            });
            field.addEventListener("change", function () {
                saveForm();
                updateCalculatedBmi();
                validateForm();
            });
        });

        updateCalculatedBmi();

        form.addEventListener("submit", function (event) {
            if (!validateForm()) {
                event.preventDefault();
                return;
            }
            saveForm();
        });
    }

    function createLinePath(points) {
        return points.map(function (point, index) {
            return (index === 0 ? "M" : "L") + " " + point.x.toFixed(1) + " " + point.y.toFixed(1);
        }).join(" ");
    }

    function createAreaPath(points, baseline) {
        if (!points.length) {
            return "";
        }
        var first = points[0];
        var last = points[points.length - 1];
        return "M " + first.x.toFixed(1) + " " + baseline.toFixed(1) + " " +
            createLinePath(points) +
            " L " + last.x.toFixed(1) + " " + baseline.toFixed(1) + " Z";
    }

    function mapSeries(data, key, width, height, padding) {
        var values = data.map(function (item) {
            return Number(item[key]);
        });
        var min = Math.min.apply(Math, values);
        var max = Math.max.apply(Math, values);
        var range = max - min || 1;
        var innerWidth = width - padding.left - padding.right;
        var innerHeight = height - padding.top - padding.bottom;

        return data.map(function (item, index) {
            return {
                x: padding.left + (innerWidth / Math.max(data.length - 1, 1)) * index,
                y: height - padding.bottom - ((Number(item[key]) - min) / range) * innerHeight,
                label: item.day
            };
        });
    }

    function renderTrendChart(metric) {
        var chart = qs("#trend-chart");
        if (!chart) {
            return;
        }

        var timeline = parseJson(chart.getAttribute("data-timeline") || "[]", []);
        if (!timeline.length) {
            chart.innerHTML = "<p>No trend data available.</p>";
            return;
        }

        var width = Math.max(chart.clientWidth || 720, 320);
        var height = 260;
        var padding = { top: 16, right: 16, bottom: 42, left: 18 };
        var series = {
            aqi: { key: "aqi", color: "#ff8a1f" },
            temperature: { key: "temperature", color: "#40c4ff" },
            humidity: { key: "humidity", color: "#2dd4bf" }
        };
        var activeKeys = metric === "all" ? ["aqi", "temperature", "humidity"] : [metric];
        var axisY = height - padding.bottom;

        var grid = [0.2, 0.4, 0.6, 0.8].map(function (ratio) {
            var y = padding.top + (height - padding.top - padding.bottom) * ratio;
            return '<line x1="' + padding.left + '" y1="' + y + '" x2="' + (width - padding.right) + '" y2="' + y + '" stroke="rgba(255,255,255,0.08)" stroke-width="1" />';
        }).join("");

        var labels = timeline.map(function (item, index) {
            var x = padding.left + ((width - padding.left - padding.right) / Math.max(timeline.length - 1, 1)) * index;
            return '<text x="' + x + '" y="' + (height - 12) + '" fill="rgba(226,232,240,0.72)" font-size="11" text-anchor="middle">' + item.day + "</text>";
        }).join("");

        var paths = activeKeys.map(function (name, index) {
            var points = mapSeries(timeline, series[name].key, width, height, padding);
            var area = index === 0
                ? '<path d="' + createAreaPath(points, axisY) + '" fill="rgba(255,255,255,0.04)" />'
                : "";
            var line = '<path d="' + createLinePath(points) + '" fill="none" stroke="' + series[name].color + '" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />';
            var dots = points.map(function (point) {
                return '<circle cx="' + point.x + '" cy="' + point.y + '" r="4" fill="' + series[name].color + '" />';
            }).join("");
            return area + line + dots;
        }).join("");

        chart.innerHTML = [
            '<svg viewBox="0 0 ' + width + " " + height + '" role="img" aria-label="Environmental trend chart">',
            grid,
            '<line x1="' + padding.left + '" y1="' + axisY + '" x2="' + (width - padding.right) + '" y2="' + axisY + '" stroke="rgba(255,255,255,0.12)" stroke-width="1" />',
            paths,
            labels,
            "</svg>"
        ].join("");
    }

    function initResultPage() {
        var meter = qs(".risk-meter");
        if (meter) {
            var fill = qs(".risk-meter-fill", meter);
            var percent = Number(meter.getAttribute("data-risk-percent") || "0");
            window.setTimeout(function () {
                fill.style.width = Math.max(0, Math.min(percent, 100)) + "%";
            }, 120);
        }

        if (!qs("#trend-chart")) {
            return;
        }

        renderTrendChart("all");
        qsa(".trend-pill").forEach(function (button) {
            button.addEventListener("click", function () {
                qsa(".trend-pill").forEach(function (pill) {
                    pill.classList.remove("active");
                });
                button.classList.add("active");
                renderTrendChart(button.getAttribute("data-metric"));
            });
        });

        window.addEventListener("resize", function () {
            var active = qs(".trend-pill.active");
            renderTrendChart(active ? active.getAttribute("data-metric") : "all");
        });
    }

    function initMobileNav() {
        var toggle = qs("#nav-toggle");
        var links = qs("#nav-links");
        if (!toggle || !links) {
            return;
        }

        toggle.addEventListener("click", function (e) {
            e.stopPropagation();
            links.classList.toggle("active");
            toggle.classList.toggle("nav-active");
        });

        document.addEventListener("click", function (e) {
            if (!links.contains(e.target) && !toggle.contains(e.target)) {
                links.classList.remove("active");
                toggle.classList.remove("nav-active");
            }
        });

        qsa(".nav-link", links).forEach(function (link) {
            link.addEventListener("click", function () {
                links.classList.remove("active");
                toggle.classList.remove("nav-active");
            });
        });
    }

    initHeader();
    initMobileNav();
    initAssessmentForm();
    initResultPage();
})();
