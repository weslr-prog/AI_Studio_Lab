from kernel.contracts import AcceptanceSpec, ArtifactSpec, ObjectiveSpec


def compile_objective_spec(objective: str) -> ObjectiveSpec:
    lowered = objective.lower()
    objective_type = "godot-2d" if "godot" in lowered or "2d" in lowered else "general"

    artifacts = (
        ArtifactSpec(
            path="projects/sandbox_project/project.godot",
            kind="project",
            owner_agent="director",
        ),
        ArtifactSpec(
            path="projects/sandbox_project/scenes/Main.tscn",
            kind="scene",
            owner_agent="architect",
        ),
        ArtifactSpec(
            path="projects/sandbox_project/scripts/player.gd",
            kind="script",
            owner_agent="programmer",
        ),
    )

    checks = [
        "project.godot exists",
        "Main.tscn exists",
        "player.gd exists",
        "godot validation has zero errors",
    ]
    if "hello world" in lowered:
        checks.append("Main scene contains Label text Hello World")

    spec = ObjectiveSpec(
        objective=objective,
        objective_type=objective_type,
        artifacts=artifacts,
        acceptance=AcceptanceSpec(
            description="Deterministic objective acceptance criteria",
            checks=tuple(checks),
        ),
    )
    spec.validate()
    return spec
