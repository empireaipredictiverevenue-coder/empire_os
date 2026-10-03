from empire_os.intelligence_optimization_fabric import build_optimization_fabric_plan
from empire_os.optimization_problem_factory import build_problem_ir
from empire_os.optimization_runtime import execute_primary_solver
from empire_os.solver_adapters.greedy_binary import is_safe_monotone_greedy_problem, solve_greedy_binary

def _problem(count=3):
    variables=[{"variable":f"x::{i}","evidence_refs":[f"ev:{i}"]} for i in range(count)]
    return build_problem_ir(
        workload_key="greedy_fixture", workload_type="future_workload",
        source_schema_version="fixture.v1", variable_type="BINARY",
        variables=variables,
        objective={"sense":"MAXIMIZE","linear":{f"x::{i}":v for i,v in enumerate(range(count,0,-1))},"quadratic":{}},
        constraints=[{"name":"choose_one","coefficients":{r["variable"]:1 for r in variables},"sense":"<=","rhs":1}],
    )

def test_generic_greedy_returns_feasible_recommendation():
    result=solve_greedy_binary(_problem())
    assert result["status"]=="AVAILABLE"
    assert result["selected_variables"]==["x::0"]
    assert result["constraints_satisfied"] is True
    assert result["optimal_for_normalized_problem"] is False
    assert result["execution_authority"]=="none"

def test_generic_greedy_rejects_non_monotone_constraint():
    problem=_problem()
    problem["constraints"][0]["sense"]=">="
    assert is_safe_monotone_greedy_problem(problem) is False
    assert solve_greedy_binary(problem)["status"]=="UNAVAILABLE"

def test_router_and_runtime_agree_on_large_greedy_fallback_when_cp_sat_unavailable():
    problem=_problem(25)
    runtime={
        "packages":{"ortools":False,"pyomo":False,"dimod":False,"dwave_samplers":False,"dwave_system":False,"qiskit":False,"pennylane":False,"amazon_braket":False,"cirq":False},
        "provider_flags":{"ibm_quantum":False,"dwave":False,"amazon_braket":False},
        "empire_adapters":{"ortools_cp_sat":True,"pyomo_mip":False,"local_bqm_quantum_inspired":True,"dwave_hybrid_cqm":False,"ibm_qaoa":False,"amazon_braket_qaoa":False,"pennylane_qaoa":False},
    }
    plan=build_optimization_fabric_plan(problem,runtime=runtime,exact_variable_limit=24)
    assert plan["primary_solver"]=="classical_greedy_reference"
    assert plan["solver_execution_ready"] is True
    executed=execute_primary_solver(plan)
    assert executed["status"]=="AVAILABLE"
    assert executed["result"]["constraints_satisfied"] is True
