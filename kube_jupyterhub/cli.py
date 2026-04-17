#!/usr/bin/env python3
import argparse
import shlex
import subprocess
import sys


DEFAULT_NAMESPACE = "jupyterhub"
DEFAULT_RELEASE = "jupyterhub"
DEFAULT_VALUES = "config.yaml"


def run(cmd: list[str], check: bool = True) -> int:
    print(f"[CMD] {shlex.join(cmd)}")
    proc = subprocess.run(cmd)
    if check and proc.returncode != 0:
        sys.exit(proc.returncode)
    return proc.returncode


def apply_config(args: argparse.Namespace) -> None:
    print("[INFO] Applying JupyterHub config...")

    run([
        "helm", "upgrade", "--install",
        args.release, "jupyterhub/jupyterhub",
        "--namespace", args.namespace,
        "--create-namespace",
        "--values", args.values,
    ])

    if args.wait:
        print("[INFO] Waiting for rollout...")
        run([
            "kubectl", "rollout", "status",
            "deploy/hub",
            "-n", args.namespace,
        ])

    print("[INFO] Done.")


def refresh_user(args: argparse.Namespace) -> None:
    if args.full:
        print(f"[WARN] This will DELETE ALL DATA for user: {args.username}")
        if not args.yes:
            confirm = input("Are you sure? (yes/no): ").strip()
            if confirm != "yes":
                print("Cancelled.")
                return

    print(f"[INFO] Deleting pod for user: {args.username}")
    run([
        "kubectl", "delete", "pod",
        "-n", args.namespace,
        f"jupyter-{args.username}",
        "--ignore-not-found",
    ], check=False)

    if args.full:
        print(f"[INFO] Deleting PVC for user: {args.username}")
        run([
            "kubectl", "delete", "pvc",
            "-n", args.namespace,
            f"claim-{args.username}",
            "--ignore-not-found",
        ], check=False)
        print("[INFO] Done (environment fully reset)")
    else:
        print("[INFO] Done (PVC is preserved)")


def list_users(args: argparse.Namespace) -> None:
    run([
        "kubectl", "get", "pods",
        "-n", args.namespace,
        "-o",
        "custom-columns=NAME:.metadata.name,STATUS:.status.phase,NODE:.spec.nodeName,AGE:.metadata.creationTimestamp",
    ], check=False)


def pvc_list(args: argparse.Namespace) -> None:
    run([
        "kubectl", "get", "pvc",
        "-n", args.namespace,
    ], check=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="JupyterHub admin utility"
    )
    parser.add_argument(
        "-n", "--namespace",
        default=DEFAULT_NAMESPACE,
        help=f"Kubernetes namespace (default: {DEFAULT_NAMESPACE})",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_apply = subparsers.add_parser("apply", help="Apply JupyterHub config with Helm")
    p_apply.add_argument(
        "-r", "--release",
        default=DEFAULT_RELEASE,
        help=f"Helm release name (default: {DEFAULT_RELEASE})",
    )
    p_apply.add_argument(
        "-f", "--values",
        default=DEFAULT_VALUES,
        help=f"Values file path (default: {DEFAULT_VALUES})",
    )
    p_apply.add_argument(
        "--no-wait",
        action="store_true",
        help="Do not wait for hub rollout",
    )
    p_apply.set_defaults(func=lambda args: apply_config(
        argparse.Namespace(
            namespace=args.namespace,
            release=args.release,
            values=args.values,
            wait=not args.no_wait,
        )
    ))

    p_refresh = subparsers.add_parser("refresh", help="Restart user's server pod, keep PVC")
    p_refresh.add_argument("username", help="JupyterHub username")
    p_refresh.set_defaults(func=lambda args: refresh_user(
        argparse.Namespace(
            namespace=args.namespace,
            username=args.username,
            full=False,
            yes=False,
        )
    ))

    p_refresh_full = subparsers.add_parser(
        "refresh-full",
        help="Delete user's server pod and PVC",
    )
    p_refresh_full.add_argument("username", help="JupyterHub username")
    p_refresh_full.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )
    p_refresh_full.set_defaults(func=lambda args: refresh_user(
        argparse.Namespace(
            namespace=args.namespace,
            username=args.username,
            full=True,
            yes=args.yes,
        )
    ))

    p_list = subparsers.add_parser("list", help="List JupyterHub user pods")
    p_list.set_defaults(func=list_users)

    p_pvc = subparsers.add_parser("pvc", help="List PVCs")
    p_pvc.set_defaults(func=pvc_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
