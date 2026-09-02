import {
  addMemberAction,
  removeMemberAction,
  renameWorkspaceAction,
  updateMemberAction,
} from "@/app/actions";
import { CopyableId } from "@/components/copyable-id";
import { MembersIcon } from "@/components/icons";
import { SubmitButton } from "@/components/submit-button";
import { getMembers, loadWorkspaceContext } from "@/lib/api";

interface MembersPageProps {
  params: Promise<{ workspaceId: string }>;
  searchParams: Promise<{ error?: string }>;
}

export default async function MembersPage({ params, searchParams }: MembersPageProps) {
  const { workspaceId } = await params;
  const { error } = await searchParams;
  const { workspace, canAdminister } = await loadWorkspaceContext(workspaceId);
  const members = await getMembers(workspaceId);
  const returnTo = `/workspaces/${workspace.id}/members`;

  return (
    <div className="app-content wide">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Access control</p>
          <h1 className="display-2">Members</h1>
        </div>
        <span className="count">{members.length}</span>
      </div>
      {error ? (
        <p className="alert" role="alert" style={{ marginBottom: 20 }}>
          {error}
        </p>
      ) : null}

      <div className="content-split">
        <section>
          <div className="row-list">
            {members.map((member) => (
              <article className="row" key={member.user_id}>
                <span className="avatar">{initials(member.display_name)}</span>
                <span className="row-identity">
                  <strong>{member.display_name}</strong>
                  <span className="row-meta">{member.email}</span>
                </span>
                {canAdminister ? (
                  <form action={updateMemberAction} className="inline-form">
                    <input name="workspaceId" type="hidden" value={workspace.id} />
                    <input name="userId" type="hidden" value={member.user_id} />
                    <input name="version" type="hidden" value={member.version} />
                    <input name="redirectTo" type="hidden" value={returnTo} />
                    <label className="sr-only" htmlFor={`role-${member.user_id}`}>
                      Role
                    </label>
                    <select defaultValue={member.role} id={`role-${member.user_id}`} name="role">
                      <option value="viewer">viewer</option>
                      <option value="member">member</option>
                      <option value="admin">admin</option>
                      <option value="owner">owner</option>
                    </select>
                    <SubmitButton>Save</SubmitButton>
                  </form>
                ) : (
                  <span className="pill">{member.role}</span>
                )}
                {canAdminister ? (
                  <form action={removeMemberAction}>
                    <input name="workspaceId" type="hidden" value={workspace.id} />
                    <input name="userId" type="hidden" value={member.user_id} />
                    <input name="redirectTo" type="hidden" value={returnTo} />
                    <SubmitButton destructive>Remove</SubmitButton>
                  </form>
                ) : null}
              </article>
            ))}
            {members.length === 0 ? (
              <div className="empty-state">
                <span className="empty-icon">
                  <MembersIcon />
                </span>
                <strong>No members yet</strong>
              </div>
            ) : null}
          </div>
        </section>

        <aside className="stack-lg">
          {canAdminister ? (
            <div className="panel" style={{ padding: 22 }}>
              <p className="eyebrow">Grant access</p>
              <h2 className="display-3" style={{ fontSize: "1.15rem" }}>
                Add an existing user
              </h2>
              <p className="muted text-sm" style={{ marginTop: 8, marginBottom: 16 }}>
                A user must sign in once before an administrator can add them.
              </p>
              <form action={addMemberAction} className="field-group">
                <input name="workspaceId" type="hidden" value={workspace.id} />
                <input name="redirectTo" type="hidden" value={returnTo} />
                <div>
                  <label htmlFor="member-email">Email</label>
                  <input id="member-email" name="email" placeholder="bob@atlas.local" required type="email" />
                </div>
                <div>
                  <label htmlFor="member-role">Role</label>
                  <select defaultValue="member" id="member-role" name="role">
                    <option value="viewer">viewer</option>
                    <option value="member">member</option>
                    <option value="admin">admin</option>
                    <option value="owner">owner</option>
                  </select>
                </div>
                <SubmitButton>Add member</SubmitButton>
              </form>
            </div>
          ) : null}

          {canAdminister ? (
            <div className="panel" style={{ padding: 22 }}>
              <p className="eyebrow">Workspace</p>
              <h2 className="display-3" style={{ fontSize: "1.15rem" }}>
                Rename workspace
              </h2>
              <form action={renameWorkspaceAction} className="field-group" style={{ marginTop: 14 }}>
                <input name="workspaceId" type="hidden" value={workspace.id} />
                <input name="version" type="hidden" value={workspace.version} />
                <input name="redirectTo" type="hidden" value={returnTo} />
                <div>
                  <label htmlFor="rename-workspace">Workspace name</label>
                  <input
                    defaultValue={workspace.name}
                    id="rename-workspace"
                    maxLength={120}
                    minLength={2}
                    name="name"
                    required
                  />
                </div>
                <SubmitButton>Rename</SubmitButton>
              </form>
              <div style={{ marginTop: 14 }}>
                <CopyableId value={workspace.id} />
              </div>
            </div>
          ) : null}
        </aside>
      </div>
    </div>
  );
}

function initials(name: string): string {
  return name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase();
}
