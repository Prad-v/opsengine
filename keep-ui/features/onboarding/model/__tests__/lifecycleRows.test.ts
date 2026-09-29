import type { AlertCatalogEntry } from "@/features/catalog/alert-code";
import {
  buildLifecycleRows,
  findRuleForCode,
  findWorkflowForCatalog,
  ruleMatchesCode,
} from "../lifecycleRows";

const catalogEntry = (
  overrides: Partial<AlertCatalogEntry> = {}
): AlertCatalogEntry => ({
  id: 1,
  code: "DCGM_FI_DEV_GPU_TEMP",
  name: "NVIDIA GPU thermal",
  auto_run_on: "both",
  keep_workflow_id: "wf-thermal",
  ...overrides,
});

describe("ruleMatchesCode", () => {
  it("matches the quoted reserved code from the wizard CEL", () => {
    expect(
      ruleMatchesCode(
        'has(labels.code) && labels.code == "DCGM_FI_DEV_GPU_TEMP"',
        "DCGM_FI_DEV_GPU_TEMP"
      )
    ).toBe(true);
  });

  it("does not treat a longer code as a match", () => {
    expect(
      ruleMatchesCode('labels.code == "HIGH_CPU_THERMAL"', "HIGH_CPU")
    ).toBe(false);
  });
});

describe("findWorkflowForCatalog", () => {
  it("matches catalog keep_workflow_id to workflow id or raw id", () => {
    const workflows = [
      { id: "uuid-1", workflow_raw_id: "wf-thermal", name: "Notify thermal" },
    ];
    expect(findWorkflowForCatalog(workflows, "wf-thermal")?.name).toBe(
      "Notify thermal"
    );
    expect(findWorkflowForCatalog(workflows, "uuid-1")?.name).toBe(
      "Notify thermal"
    );
    expect(findWorkflowForCatalog(workflows, "missing")).toBeUndefined();
  });
});

describe("buildLifecycleRows", () => {
  it("joins catalog, correlation, and workflow into table rows", () => {
    const rows = buildLifecycleRows({
      catalog: [
        catalogEntry(),
        catalogEntry({
          id: 2,
          code: "HIGH_CPU",
          name: "High CPU",
          keep_workflow_id: null,
          auto_run_on: "none",
          disabled: true,
        }),
      ],
      rules: [
        {
          id: "rule-thermal",
          name: "DCGM_FI_DEV_GPU_TEMP incidents",
          definition_cel: 'labels.code == "DCGM_FI_DEV_GPU_TEMP"',
        },
      ],
      workflows: [
        {
          id: "wf-thermal",
          name: "Notify on DCGM_FI_DEV_GPU_TEMP",
          workflow_raw: "provider:\n  type: slack\n",
        },
      ],
      installedProviders: [
        { type: "grafana", tags: ["alert"] },
        { type: "slack", can_notify: true, tags: ["messaging"] },
      ],
    });

    expect(rows).toHaveLength(2);
    expect(rows[0].code).toBe("DCGM_FI_DEV_GPU_TEMP");
    expect(rows[0].paused).toBe(false);
    expect(rows[0].correlation?.name).toBe("DCGM_FI_DEV_GPU_TEMP incidents");
    expect(rows[0].workflow?.name).toBe("Notify on DCGM_FI_DEV_GPU_TEMP");
    expect(rows[0].notification).toBe(true);
    expect(rows[0].isComplete).toBe(true);

    expect(rows[1].code).toBe("HIGH_CPU");
    expect(rows[1].paused).toBe(true);
    expect(rows[1].correlation).toBeNull();
    expect(rows[1].workflow).toBeNull();
    expect(rows[1].isComplete).toBe(false);
  });

  it("finds the rule for a given code", () => {
    expect(
      findRuleForCode(
        [
          {
            id: "r1",
            definition_cel: 'labels.code == "HIGH_CPU"',
          },
        ],
        "HIGH_CPU"
      )?.id
    ).toBe("r1");
  });
});
