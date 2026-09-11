import {
  catalogPathToKeepTemplate,
  catalogWorkflowIdToKeepTemplate,
  getTemporalCatalogActionTemplates,
} from "../temporalCatalogSteps";

describe("temporalCatalogSteps", () => {
  it("maps catalog paths to Keep mustache templates", () => {
    expect(catalogPathToKeepTemplate("id")).toBe("{{ incident.id }}");
    expect(catalogPathToKeepTemplate("enrichments.list_path")).toBe(
      "{{ incident.enrichments.list_path }}"
    );
    expect(catalogPathToKeepTemplate("alert.name")).toBe("{{ alert.name }}");
  });

  it("converts workflow id template and bakes catalog key", () => {
    expect(
      catalogWorkflowIdToKeepTemplate(
        "incident-{{incident.id}}-{{catalog.id}}",
        "list-and-zip-directory"
      )
    ).toBe("incident-{{ incident.id }}-list-and-zip-directory");
  });

  it("builds action-temporal templates from catalog entries", () => {
    const templates = getTemporalCatalogActionTemplates(
      [
        {
          id: 1,
          catalog_key: "list-and-zip-directory",
          name: "List and Zip Directory",
          workflow_type: "ListAndZipDirectory",
          task_queue: "keep-ops",
          workflow_id_template: "incident-{{incident.id}}-{{catalog.id}}",
          input_mapping: {
            incident_id: "id",
            path: "enrichments.list_path",
          },
          provider_id: "p1",
          provider_name: "mock-temporal",
          disabled: false,
        },
      ],
      [
        {
          type: "temporal",
          can_notify: true,
          can_query: true,
          notify_params: ["operation", "workflow_type", "task_queue", "arg"],
          query_params: [],
          id: "p1",
          display_name: "Temporal",
          installed: true,
          linked: false,
          last_alert_received: "",
          details: { authentication: {}, name: "mock-temporal" },
          config: {},
          validatedScopes: {},
          tags: [],
          pulling_available: false,
          pulling_enabled: false,
          categories: [],
          coming_soon: false,
          health: false,
        } as any,
      ]
    );

    expect(templates).toHaveLength(1);
    expect(templates[0].type).toBe("action-temporal");
    expect(templates[0].name).toBe("List and Zip Directory");
    expect(templates[0].properties.config).toBe("mock-temporal");
    expect(templates[0].properties.with).toMatchObject({
      operation: "start_workflow",
      workflow_type: "ListAndZipDirectory",
      task_queue: "keep-ops",
      workflow_id: "incident-{{ incident.id }}-list-and-zip-directory",
      arg: {
        incident_id: "{{ incident.id }}",
        path: "{{ incident.enrichments.list_path }}",
      },
    });
  });
});
